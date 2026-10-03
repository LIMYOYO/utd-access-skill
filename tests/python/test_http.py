import asyncio
import gzip
import logging

import httpx
import pytest

from paper_access.http import HttpClient, NetworkFailure, UnsafeURL


async def public_resolver(host):
    return ["93.184.216.34"]


def run(coro):
    return asyncio.run(coro)


def test_401_does_not_retry_and_dns_is_pinned_with_tls_hostname():
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(401)
    async def scenario():
        async with HttpClient(transport=httpx.MockTransport(respond), resolver=public_resolver) as client:
            response = await client.request("GET", "https://papers.example/paper", provider="test")
            assert response.status_code == 401
    run(scenario())
    assert len(calls) == 1
    assert calls[0].url.host == "93.184.216.34"
    assert calls[0].headers["host"] == "papers.example"
    assert calls[0].extensions["sni_hostname"] == "papers.example"


@pytest.mark.parametrize("url", ["http://127.0.0.1/a", "http://[::1]/a", "http://169.254.169.254/a", "file:///etc/passwd", "https://user:pass@public.example/a", "http://localhost/a"])
def test_unsafe_urls_do_not_reach_transport(url):
    async def scenario():
        def respond(request):
            pytest.fail("unsafe request reached transport")
        async with HttpClient(transport=httpx.MockTransport(respond), resolver=public_resolver) as client:
            with pytest.raises(UnsafeURL):
                await client.request("GET", url, provider="test")
    run(scenario())


def test_redirect_to_private_dns_address_is_rejected():
    async def resolve(host):
        return ["10.1.2.3"] if host == "internal.example" else ["93.184.216.34"]
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(302, headers={"location": "http://internal.example/secret"})
    async def scenario():
        async with HttpClient(transport=httpx.MockTransport(respond), resolver=resolve) as client:
            with pytest.raises(UnsafeURL):
                await client.request("GET", "http://public.example/paper", provider="test")
    run(scenario())
    assert len(calls) == 1


def test_cross_origin_redirect_strips_authorization_and_cookies():
    headers = []
    def respond(request):
        headers.append(dict(request.headers))
        if len(headers) == 1:
            return httpx.Response(302, headers={"location": "https://repo.example/file", "set-cookie": "secret=value"})
        return httpx.Response(200, content=b"body")
    async def scenario():
        async with HttpClient(transport=httpx.MockTransport(respond), resolver=public_resolver) as client:
            response = await client.request("GET", "https://api.example/a", provider="test", headers={"Authorization": "Bearer secret", "Cookie": "private=value"})
            assert response.content == b"body"
    run(scenario())
    assert "authorization" not in headers[1] and "cookie" not in headers[1]


def test_transient_errors_retry_three_times_and_hide_key():
    calls = []
    async def no_sleep(delay):
        pass
    def respond(request):
        calls.append(request)
        raise httpx.ConnectError(f"failure at {request.url}")
    async def scenario():
        async with HttpClient(transport=httpx.MockTransport(respond), resolver=public_resolver, sleep=no_sleep) as client:
            with pytest.raises(NetworkFailure) as error:
                await client.request("GET", "https://api.example/a?api_key=never-print", provider="test")
            assert "never-print" not in str(error.value)
            assert error.value.__cause__ is None
    run(scenario())
    assert len(calls) == 3


def test_429_retry_after_is_shared_with_same_host_requests():
    class Clock:
        now = 0.0
        async def sleep(self, delay):
            self.now += delay
            await asyncio.sleep(0)
    clock = Clock()
    calls = []
    def respond(request):
        calls.append((request.url.path, clock.now))
        return httpx.Response(429, headers={"retry-after": "5"}) if len(calls) == 1 else httpx.Response(200)
    async def scenario():
        async with HttpClient(transport=httpx.MockTransport(respond), resolver=public_resolver,
                              sleep=clock.sleep, monotonic=lambda: clock.now) as client:
            results = await asyncio.gather(client.request("GET", "https://api.example/a", provider="test"),
                                           client.request("GET", "https://api.example/b", provider="test"))
            assert [r.status_code for r in results] == [200, 200]
    run(scenario())
    assert all(instant >= 5 for _, instant in calls[1:])


def test_compressed_response_is_not_decoded_twice():
    def respond(request):
        return httpx.Response(200, headers={"content-encoding": "gzip", "content-type": "application/json"}, content=gzip.compress(b'{"ok":true}'))
    async def scenario():
        async with HttpClient(transport=httpx.MockTransport(respond), resolver=public_resolver) as client:
            result = await client.request("GET", "https://api.example/paper", provider="test")
            assert result.json() == {"ok": True}
    run(scenario())


def test_httpx_info_logging_does_not_leak_api_key(caplog):
    caplog.set_level(logging.INFO, logger="httpx")
    async def scenario():
        async with HttpClient(transport=httpx.MockTransport(lambda request: httpx.Response(200)), resolver=public_resolver) as client:
            await client.request("GET", "https://api.example/paper?api_key=private-secret", provider="test")
    run(scenario())
    assert "private-secret" not in caplog.text


def test_limited_host_waiters_do_not_block_healthy_host():
    async def scenario():
        waiting = asyncio.Event()
        release = asyncio.Event()
        counts = {}
        async def sleep(delay):
            waiting.set()
            await release.wait()
        def respond(request):
            host = request.headers["host"]
            counts[host] = counts.get(host, 0) + 1
            if host == "limited.example" and counts[host] == 1:
                return httpx.Response(429, headers={"retry-after": "5"})
            return httpx.Response(200)
        async with HttpClient(transport=httpx.MockTransport(respond), resolver=public_resolver, sleep=sleep) as client:
            first = asyncio.create_task(client.request("GET", "https://limited.example/a", provider="test"))
            await waiting.wait()
            second = asyncio.create_task(client.request("GET", "https://limited.example/b", provider="test"))
            await asyncio.sleep(0)
            try:
                response = await asyncio.wait_for(client.request("GET", "https://healthy.example/a", provider="test"), timeout=0.5)
                assert response.status_code == 200
            finally:
                release.set()
                await asyncio.gather(first, second)
    run(scenario())


def test_hour_long_retry_after_returns_to_runner_without_sleeping():
    async def reject_sleep(delay):
        raise AssertionError("long cooldown must be persisted instead of blocking the task")
    async def scenario():
        async with HttpClient(transport=httpx.MockTransport(lambda request: httpx.Response(429, headers={"retry-after": "3600"})), resolver=public_resolver, sleep=reject_sleep) as client:
            response = await client.request("GET", "https://api.example/a", provider="test")
            assert response.status_code == 429
    run(scenario())
