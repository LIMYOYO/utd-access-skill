"""Bounded HTTP with host-wide backoff, public-address pinning and safe errors."""

from contextlib import asynccontextmanager
import asyncio
import ipaddress
import logging
import os
import random
import re
import socket
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin

import httpx


class _HTTPLogFilter(logging.Filter):
    """HTTPX logs request URLs at INFO; strip all query values at the source."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = re.sub(r"(https?://[^\s?\"']+)\?[^\s\"']+", r"\1?[redacted]", record.getMessage())
        record.args = ()
        return True


class NetworkFailure(RuntimeError):
    pass


class UnsafeURL(NetworkFailure):
    pass


class RateLimited(NetworkFailure):
    def __init__(self, remaining: float):
        self.next_retry_at = time.time() + remaining
        super().__init__("source is waiting for its retry window")


async def resolve_public(host: str) -> list[str]:
    records = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(record[4][0] for record in records))


def _retry_after(value: str | None) -> float:
    if not value:
        return 0
    try:
        return max(0, float(value))
    except ValueError:
        try:
            date = parsedate_to_datetime(value)
            return max(0, (date - datetime.now(timezone.utc)).total_seconds())
        except (ValueError, TypeError, OverflowError):
            return 0


@asynccontextmanager
async def _unlimited_slot():
    yield


class HttpClient:
    def __init__(self, *, transport=None, resolver=resolve_public, sleep=asyncio.sleep,
                 monotonic=time.monotonic):
        logger = logging.getLogger("httpx")
        if not any(isinstance(item, _HTTPLogFilter) for item in logger.filters):
            logger.addFilter(_HTTPLogFilter())
        from .config import data_directory
        from .source_gate import SourceGate
        self._source_gate = SourceGate(data_directory() / "source-limits.sqlite3") if transport is None else None
        self.event_hook = None
        self._transport = transport
        self._resolver = resolver
        self._sleep = sleep
        self._now = monotonic
        self._clients: dict[tuple, httpx.AsyncClient] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._cooldown: dict[str, float] = {}
        self._metadata = asyncio.Semaphore(2)
        self._fulltext = asyncio.Semaphore(4)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        for client in self._clients.values():
            await client.aclose()

    async def _address(self, url: httpx.URL) -> str:
        if url.scheme not in {"http", "https"} or not url.host or url.username or url.password:
            raise UnsafeURL("unsupported URL scheme or embedded credentials")
        host = url.host.rstrip(".").lower()
        if host == "localhost" or host.endswith((".localhost", ".local")):
            raise UnsafeURL("local address is not allowed")
        try:
            literal = ipaddress.ip_address(host)
        except ValueError:
            try:
                addresses = await self._resolver(host)
            except OSError:
                raise NetworkFailure("DNS resolution failed") from None
        else:
            addresses = [str(literal)]
        if not addresses:
            raise NetworkFailure("DNS returned no addresses")
        for address in addresses:
            try:
                ip = ipaddress.ip_address(address)
            except ValueError:
                raise UnsafeURL("DNS returned an invalid address") from None
            if not ip.is_global or ip.is_multicast or "%" in address:
                raise UnsafeURL("private or reserved destination is not allowed")
        return addresses[0]

    async def request(self, method: str, url: str, *, provider: str, **kwargs) -> httpx.Response:
        start = self._now()
        event = {"provider": provider, "status_code": None, "error": None}
        try:
            response = await self._request(method, url, provider=provider, **kwargs)
            event["status_code"] = response.status_code
            return response
        except BaseException as error:
            event["error"] = type(error).__name__
            raise
        finally:
            event["elapsed_seconds"] = max(0, self._now() - start)
            if self.event_hook:
                self.event_hook(event)

    async def _request(self, method: str, url: str, *, provider: str, params=None,
                      headers=None, fulltext: bool = False, max_bytes: int = 10 * 1024 * 1024,
                      destination: Path | None = None, max_attempts: int = 3, follow_redirects: bool = True) -> httpx.Response:
        if max_attempts not in {1, 2, 3} or max_bytes <= 0:
            raise ValueError("invalid request bounds")
        if method.upper() not in {"GET", "HEAD"}:
            raise ValueError("only read-only HTTP methods are supported")
        try:
            current = httpx.URL(url, params=params) if params is not None else httpx.URL(url)
        except (httpx.InvalidURL, ValueError):
            raise UnsafeURL("invalid URL") from None
        request_headers = httpx.Headers(headers or {})
        request_headers.setdefault("User-Agent", "utd-paper-access/0.6.1 (local research tool)")
        if destination is not None:
            request_headers["Accept-Encoding"] = "identity"
        resume_etag = None
        resume_url = None
        resume_offset = 0
        resume_total = None
        semaphore = self._fulltext if fulltext else self._metadata
        for redirect in range(6):
            address = await self._address(current)
            origin = (current.scheme, current.host, current.port)
            # A distinct pool per original origin prevents TLS reuse across
            # unrelated hostnames sharing the same resolved IP address.
            if origin not in self._clients:
                self._clients[origin] = httpx.AsyncClient(transport=self._transport, trust_env=False,
                                                        timeout=30, follow_redirects=False)
            client = self._clients[origin]
            lock = self._locks.setdefault(current.host, asyncio.Lock())
            async with lock:
                for attempt in range(max_attempts):
                    delay = self._cooldown.get(current.host, 0) - self._now()
                    if delay > 5:
                        raise RateLimited(delay)
                    if delay > 0:
                        await self._sleep(delay)
                    if resume_etag and resume_url == str(current) and resume_offset:
                        request_headers["Range"] = f"bytes={resume_offset}-"
                        request_headers["If-Range"] = resume_etag
                    elif destination is not None:
                        request_headers.pop("Range", None)
                        request_headers.pop("If-Range", None)
                    pinned = current.copy_with(host=address)
                    request_headers["Host"] = current.netloc.decode("ascii")
                    request = client.build_request(method, pinned, headers=request_headers,
                                                   extensions={"sni_hostname": current.host})
                    try:
                        async with semaphore, (self._source_gate.slot("arxiv", 3) if self._source_gate and current.host in {"arxiv.org", "export.arxiv.org", "www.arxiv.org"} else _unlimited_slot()):
                            response = await client.send(request, stream=True)
                            output = None
                            try:
                                body = bytearray()
                                received = 0
                                expected_range_end = None
                                if destination is not None and response.status_code == 206:
                                    content_range = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", response.headers.get("content-range", ""))
                                    if (not content_range or not resume_etag or resume_url != str(current)
                                            or response.headers.get("etag") != resume_etag
                                            or int(content_range[1]) != resume_offset
                                            or int(content_range[2]) + 1 != int(content_range[3])
                                            or (resume_total is not None and int(content_range[3]) != resume_total)
                                            or response.headers.get("content-encoding", "identity") != "identity"):
                                        resume_etag, resume_offset, resume_total = None, 0, None
                                        raise httpx.ProtocolError("invalid range response")
                                    received = resume_offset
                                    expected_range_end = int(content_range[3])
                                    resume_total = expected_range_end
                                    output = destination.open("ab", buffering=0)
                                elif destination is not None and response.status_code == 200:
                                    etag = response.headers.get("etag", "")
                                    resume_etag = etag if (etag.startswith('"') and etag.endswith('"')
                                                          and response.headers.get("accept-ranges", "").lower() == "bytes"
                                                          and response.headers.get("content-encoding", "identity") == "identity") else None
                                    resume_url, resume_offset = str(current), 0
                                    length = response.headers.get("content-length", "")
                                    resume_total = int(length) if length.isascii() and length.isdigit() else None
                                    destination.parent.mkdir(parents=True, exist_ok=True)
                                    output = destination.open("wb", buffering=0)
                                async for chunk in response.aiter_bytes():
                                    received += len(chunk)
                                    if received > max_bytes:
                                        raise NetworkFailure("response exceeds size limit")
                                    if output is None:
                                        body.extend(chunk)
                                    else:
                                        output.write(chunk)
                                if output is not None:
                                    if expected_range_end is not None and received != expected_range_end:
                                        raise httpx.ProtocolError("incomplete range response")
                                    os.fsync(output.fileno())
                                status, response_headers = response.status_code, response.headers
                            finally:
                                if output is not None:
                                    output.close()
                                await response.aclose()
                    except httpx.HTTPError:
                        if destination is not None and resume_etag and destination.is_file():
                            resume_offset = destination.stat().st_size
                        if attempt == max_attempts - 1:
                            raise NetworkFailure(f"{provider}: transport failed after {max_attempts} attempts") from None
                        self._cooldown[current.host] = self._now() + 2 ** attempt + random.random()
                        continue
                    if status == 429 or status in {500, 502, 503, 504}:
                        retry_delay = max(_retry_after(response_headers.get("retry-after")), 2 ** attempt + random.random())
                        self._cooldown[current.host] = self._now() + retry_delay
                        if self._source_gate and current.host in {"arxiv.org", "export.arxiv.org", "www.arxiv.org"}:
                            self._source_gate.defer("arxiv", retry_delay)
                        if attempt < max_attempts - 1 and self._cooldown[current.host] - self._now() <= 5:
                            continue
                    # A sanitized request prevents exception/report consumers
                    # from accidentally printing API keys in query strings.
                    safe_request = httpx.Request(method, current.copy_with(query=None))
                    decoded_headers = {key: value for key, value in response_headers.items()
                                       if key.lower() not in {"content-encoding", "content-length", "transfer-encoding"}}
                    result = httpx.Response(status, headers=decoded_headers, content=bytes(body), request=safe_request)
                    break
            if not follow_redirects or result.status_code not in {301, 302, 303, 307, 308} or "location" not in result.headers:
                return result
            if redirect == 5:
                raise NetworkFailure("redirect limit exceeded")
            try:
                target = httpx.URL(urljoin(str(current), result.headers["location"]))
            except (ValueError, httpx.InvalidURL):
                raise UnsafeURL("invalid redirect URL") from None
            if current.scheme == "https" and target.scheme == "http":
                raise UnsafeURL("HTTPS downgrade redirect rejected")
            if (target.scheme, target.host, target.port) != origin:
                request_headers = httpx.Headers({key: value for key, value in request_headers.items()
                                                if key.lower() in {"user-agent", "accept", "accept-encoding", "range", "if-range"}})
            current = target
        raise NetworkFailure("request did not produce a response")
