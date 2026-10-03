from dataclasses import replace
from paper_access.matching import match_identity
from paper_access.models import PaperInput


def test_title_without_authors_never_auto_resolves(expected_paper):
    query = replace(expected_paper, identifier_kind="title", identifier=expected_paper.title, authors=())
    assert match_identity(query, [expected_paper]) == []


def test_same_title_different_author_is_not_match(expected_paper):
    assert match_identity(expected_paper, [replace(expected_paper, authors=("Other Author",))]) == []


def test_exact_title_all_authors_and_year_match(expected_paper):
    assert match_identity(expected_paper, [expected_paper]) == [expected_paper]
    assert match_identity(expected_paper, [replace(expected_paper, year=2010)]) == []


def test_nber_input_preserves_platform_id_and_resolves_doi(expected_paper):
    paper = replace(expected_paper, identifier_kind="nber", identifier="w12345")
    assert paper.doi == "10.3386/w12345"
    assert paper.identifier_kind == "nber"


def test_resolved_title_keeps_input_identity(expected_paper):
    query = replace(expected_paper, identifier_kind="title", identifier=expected_paper.title)
    enriched = replace(query, resolved_doi="10.1234/queues")
    assert query.paper_id == enriched.paper_id
    assert enriched.doi == "10.1234/queues"


def test_version_links_keep_separate_identity_and_evidence(tmp_path):
    from paper_access.matching import link_versions
    from paper_access.store import JobStore
    store = JobStore(tmp_path / "db")
    link_versions("arxiv:1811.06128v2", "doi:10.1016/j.ejor.2020.07.063",
                  {"source": "https://export.arxiv.org/api/query", "method": "arxiv_doi_field"}, store)
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM version_relations").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == 0


def test_matcher_preserves_individual_author_boundaries(expected_paper):
    query = replace(expected_paper, authors=("John Smith", "Jane Ann Jones"))
    record = replace(expected_paper, authors=("John Smith Jane", "Ann Jones"))
    assert match_identity(query, [record]) == []
