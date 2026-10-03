import asyncio
from dataclasses import replace
from urllib.parse import urlsplit, parse_qs
import pytest
from paper_access.institution import build_access_links, import_file
from paper_access.models import JobOptions
from paper_access.store import JobStore


def test_institution_links_are_scoped_and_encoded(expected_paper):
    a = build_access_links(expected_paper, {"institution_name": "A", "resolver_base_url": "https://a.example/openurl"})
    b = build_access_links(expected_paper, {"institution_name": "B", "resolver_base_url": "https://b.example/openurl"})
    assert "a.example" in a[-1]["url"] and "a.example" not in str(b)
    assert parse_qs(urlsplit(a[-1]["url"]).query)["rft_id"] == ["info:doi/10.1234/queues"]
    assert build_access_links(expected_paper, None)


def test_unsafe_profile_link_is_rejected(expected_paper):
    with pytest.raises(ValueError):
        build_access_links(expected_paper, {"resolver_base_url": "javascript:alert(1)"})


def test_manual_import_validates_file_and_is_idempotent(tmp_path, expected_paper, pdf_file):
    store = JobStore(tmp_path / "db")
    job = store.create([expected_paper], [], JobOptions(tmp_path / "out"))
    source = pdf_file()
    assert import_file(job, expected_paper.paper_id, source.path, store, version="acceptedVersion") == 0
    assert import_file(job, expected_paper.paper_id, source.path, store, version="acceptedVersion") == 0
    assert store.snapshot(job)["verified_count"] == 1
    assert len(store.snapshot(job)["artifacts"]) == 1
    wrong = pdf_file(name="wrong.pdf", author="Other Author")
    assert import_file(job, expected_paper.paper_id, wrong.path, store, version="acceptedVersion") == 2
    assert store.snapshot(job)["verified_count"] == 1


def test_manual_import_cannot_bypass_published_only(tmp_path, expected_paper, pdf_file):
    store = JobStore(tmp_path / "db")
    job = store.create([expected_paper], [], JobOptions(tmp_path / "out", version_policy="published-only"))
    assert import_file(job, expected_paper.paper_id, pdf_file().path, store, version="acceptedVersion") == 2
    assert store.snapshot(job)["verified_count"] == 0
