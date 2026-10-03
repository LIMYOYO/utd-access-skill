from paper_access.capabilities import capabilities


def test_unprovisioned_institution_apis_cannot_claim_bulk_support():
    rows=capabilities()
    for row in rows:
        for key in ("metadata","reading_download","bulk_download","tdm","ai_processing","retention","credentials_required","checked_at","evidence_url","live_test_status"):
            assert key in row
    for row in rows:
        if row["provider"] in {"eds","elsevier","wiley","sage","springer","core","repec"}:
            assert row["enabled"] is False
            assert row["bulk_download"] != "allowed"
