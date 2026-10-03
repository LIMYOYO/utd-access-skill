from hashlib import sha256
from dataclasses import replace
import pytest

from paper_access.models import Artifact
from paper_access.validate import validate_artifact


def artifact(path, text, mime):
    path.write_text(text)
    data = path.read_bytes()
    return Artifact(path, sha256(data).hexdigest(), mime, len(data))


def test_correct_pdf_title_authors_and_body_are_verified(pdf_file, expected_paper, candidate):
    result = validate_artifact(pdf_file(), expected_paper, candidate)
    assert result.status == "verified_fulltext"
    assert result.pages == 2
    assert result.identity_evidence == "title_and_authors"


def test_wrong_author_with_same_title_is_ambiguous(pdf_file, expected_paper, candidate):
    result = validate_artifact(pdf_file(author="Unrelated Author"), expected_paper, candidate)
    assert result.status == "ambiguous_match"


def test_doi_in_references_does_not_prove_identity(pdf_file, expected_paper, candidate):
    paper = pdf_file(title="A Different Study", author="Other Researcher", body=["A discussion of unrelated research questions." * 30, "References", "doi:10.1234/queues"])
    assert validate_artifact(paper, expected_paper, candidate).status == "ambiguous_match"


def test_truncated_pdf_not_verified(pdf_file, expected_paper, candidate):
    paper = pdf_file()
    paper.path.write_bytes(paper.path.read_bytes()[:-40])
    result = validate_artifact(paper, expected_paper, candidate)
    assert result.status != "verified_fulltext"
    assert result.reason_code == "file_integrity_mismatch"


def test_truncated_pdf_with_matching_download_hash_still_fails(pdf_file, expected_paper, candidate):
    paper = pdf_file()
    data = paper.path.read_bytes()[:-40]
    paper.path.write_bytes(data)
    paper = replace(paper, sha256=sha256(data).hexdigest(), byte_count=len(data))
    result = validate_artifact(paper, expected_paper, candidate)
    assert result.reason_code == "invalid_document"


def test_login_html_cannot_be_pdf_success(tmp_path, expected_paper, candidate):
    paper = artifact(tmp_path / "login.pdf", '<html><form><input type="password">Sign in</form></html>', "application/pdf")
    result = validate_artifact(paper, expected_paper, candidate)
    assert result.status != "verified_fulltext"


def test_abstract_only_html_not_fulltext(tmp_path, expected_paper, candidate):
    paper = artifact(tmp_path / "abstract.html", '<html><meta name="citation_doi" content="10.1234/queues"><h1>Queueing and Service Systems</h1><div class="abstract">A short abstract.</div></html>', "text/html")
    assert validate_artifact(paper, expected_paper, candidate).reason_code == "not_fulltext"


def test_supplement_is_not_main_article(pdf_file, expected_paper, candidate):
    paper = pdf_file(title="Supplementary material: Queueing and Service Systems")
    assert validate_artifact(paper, expected_paper, candidate).reason_code == "supplementary_material"


def test_valid_jats_article_has_primary_doi_evidence(tmp_path, expected_paper, candidate):
    xml = '<article><front><article-meta><article-id pub-id-type="doi">10.1234/queues</article-id></article-meta></front><body><sec><title>Introduction</title><p>' + 'We examine capacity allocation and queueing delays. ' * 40 + '</p></sec></body></article>'
    paper = artifact(tmp_path / "article.xml", xml, "application/xml")
    result = validate_artifact(paper, expected_paper, candidate)
    assert result.status == "verified_fulltext" and result.identity_evidence == "primary_doi"


def test_xml_external_entity_is_rejected(tmp_path, expected_paper, candidate):
    xml = '<!DOCTYPE article [<!ENTITY secret SYSTEM "file:///etc/passwd">]><article><body>&secret;</body></article>'
    paper = artifact(tmp_path / "unsafe.xml", xml, "application/xml")
    assert validate_artifact(paper, expected_paper, candidate).reason_code == "invalid_document"


def test_legacy_pdf_with_duplicate_identical_font_dictionary_key_is_readable(pdf_file, expected_paper, candidate):
    paper = pdf_file()
    data = paper.path.read_bytes().replace(b"/BaseFont /Helvetica", b"/BaseFont /Helvetica /BaseFont /Helvetica")
    paper.path.write_bytes(data)
    paper = replace(paper, sha256=sha256(data).hexdigest(), byte_count=len(data))
    result = validate_artifact(paper, expected_paper, candidate)
    assert result.status == "verified_fulltext"


def test_long_abstract_in_article_wrapper_is_not_fulltext(tmp_path, expected_paper, candidate):
    html = '<meta name="citation_doi" content="10.1234/queues"><article><h1>Queueing and Service Systems</h1><h2>Abstract</h2><p>' + 'This abstract describes interesting findings. ' * 40 + '</p><a>Purchase full text</a></article>'
    paper = artifact(tmp_path / "abstract.html", html, "text/html")
    assert validate_artifact(paper, expected_paper, candidate).status != "verified_fulltext"


def test_surname_substring_does_not_match_author(pdf_file, expected_paper, candidate):
    paper = pdf_file(author="John Goldsmith")
    assert validate_artifact(paper, expected_paper, candidate).status == "ambiguous_match"


def test_comment_title_containing_original_title_is_not_same_paper(pdf_file, expected_paper, candidate):
    paper = pdf_file(title="A Comment on Queueing and Service Systems")
    assert validate_artifact(paper, expected_paper, candidate).status == "ambiguous_match"


def test_tei_related_item_doi_cannot_override_main_doi(tmp_path, expected_paper, candidate):
    xml = '<TEI><teiHeader><fileDesc><titleStmt><title>Different study</title></titleStmt><publicationStmt><idno type="DOI">10.5678/unrelated</idno></publicationStmt><sourceDesc><bibl><relatedItem><bibl><idno type="DOI">10.1234/queues</idno></bibl></relatedItem></bibl></sourceDesc></fileDesc></teiHeader><text><body><div><p>' + 'A completely different study is presented here. ' * 40 + '</p></div></body></text></TEI>'
    paper = artifact(tmp_path / "related.xml", xml, "application/xml")
    assert validate_artifact(paper, expected_paper, candidate).status == "ambiguous_match"


def test_long_pdf_abstract_without_body_is_not_fulltext(pdf_file, expected_paper, candidate):
    paper = pdf_file()
    data = paper.path.read_bytes().replace(b"1 Introduction", b"More abstract ")
    paper.path.write_bytes(data)
    paper = replace(paper, sha256=sha256(data).hexdigest(), byte_count=len(data))
    assert validate_artifact(paper, expected_paper, candidate).reason_code == "not_fulltext"


def test_explicit_accepted_manuscript_conflicts_with_published_candidate(pdf_file, expected_paper, candidate):
    paper = pdf_file(author="Jane Smith - Accepted Manuscript")
    result = validate_artifact(paper, expected_paper, replace(candidate, version="publishedVersion"))
    assert result.status != "verified_fulltext"
    assert result.reason_code == "version_evidence_conflict"


def test_ssrn_banner_url_does_not_truncate_article_header(pdf_file, expected_paper, candidate):
    paper = pdf_file(title="Electronic copy available at: http://ssrn.com/abstract=2796566\nQueueing and Service Systems")
    assert validate_artifact(paper, expected_paper, candidate).status == "verified_fulltext"


def test_ssrn_banner_does_not_make_comment_title_match(pdf_file, expected_paper, candidate):
    paper = pdf_file(title="Electronic copy available at: https://ssrn.com/abstract=2796566\nA Comment on Queueing and Service Systems")
    assert validate_artifact(paper, expected_paper, candidate).status == "ambiguous_match"


def test_explicit_ssrn_banner_id_must_match_ssrn_input(pdf_file, expected_paper, candidate):
    expected = replace(expected_paper, identifier_kind="ssrn", identifier="12345")
    paper = pdf_file(title="Electronic copy available at: https://ssrn.com/abstract=99999\nQueueing and Service Systems")
    result = validate_artifact(paper, expected, replace(candidate, paper_id=expected.paper_id))
    assert result.reason_code == "primary_identifier_mismatch"


@pytest.mark.parametrize("prefix", ["Invited Review", "arXiv:1811.06128v2 [cs.LG] 12 Mar 2020"])
def test_recognized_document_label_is_separate_from_title(pdf_file, expected_paper, candidate, prefix):
    paper = pdf_file(title=prefix + "\nQueueing and Service Systems")
    assert validate_artifact(paper, expected_paper, candidate).status == "verified_fulltext"


def test_wrapped_comment_prefix_is_not_ignored(pdf_file, expected_paper, candidate):
    paper = pdf_file(title="A Comment on\nQueueing and Service Systems")
    assert validate_artifact(paper, expected_paper, candidate).status == "ambiguous_match"


def test_surname_first_full_author_line_matches(pdf_file, expected_paper, candidate):
    expected = replace(expected_paper, authors=("Jorne Van den Bergh", "Jeroen Beliën"))
    paper = pdf_file(author="Van den Bergh Jorne\nBeliën Jeroen")
    assert validate_artifact(paper, expected, candidate).status == "verified_fulltext"


def test_explicit_arxiv_identifier_conflict_is_not_ignored(pdf_file, expected_paper, candidate):
    expected = replace(expected_paper, identifier_kind="arxiv", identifier="1811.06128v1")
    paper = pdf_file(title="arXiv:1811.06128v2 [cs.LG] 12 Mar 2020\nQueueing and Service Systems")
    result = validate_artifact(paper, expected, replace(candidate, paper_id=expected.paper_id))
    assert result.reason_code == "primary_identifier_mismatch"


def test_arxiv_footer_version_conflict_is_not_ignored(pdf_file, expected_paper, candidate):
    expected = replace(expected_paper, identifier_kind="arxiv", identifier="1811.06128v1")
    paper = pdf_file(body=["arXiv:1811.06128v2 [cs.LG] 12 Mar 2020"] + ["Long main article body. " * 10] * 15)
    result = validate_artifact(paper, expected, replace(candidate, paper_id=expected.paper_id))
    assert result.reason_code == "primary_identifier_mismatch"


def test_author_comma_preserves_explicit_surname(pdf_file, expected_paper, candidate):
    expected = replace(expected_paper, authors=("Smith, John Paul",))
    paper = pdf_file(author="Paul, Smith John")
    assert validate_artifact(paper, expected, candidate).status == "ambiguous_match"


def test_article_identity_after_two_cover_pages(pdf_file, expected_paper, candidate):
    paper = pdf_file(front_matter=("University Repository\nReport 2024-01", "Copyright 2024. Research institute report."))
    assert validate_artifact(paper, expected_paper, candidate).status == "verified_fulltext"


def test_later_identity_does_not_override_conflicting_cover_doi(pdf_file, expected_paper, candidate):
    paper = pdf_file(front_matter=("Repository copy\ndoi:10.5678/unrelated",))
    assert validate_artifact(paper, expected_paper, candidate).reason_code == "primary_doi_mismatch"


def test_later_citation_cannot_supply_article_identity(pdf_file, expected_paper, candidate):
    paper = pdf_file(title="Different Research", author="Other Author", body=["Discussion of a separate article. " * 5] * 15 + ["Queueing and Service Systems", "Jane Smith"])
    assert validate_artifact(paper, expected_paper, candidate).status == "ambiguous_match"


def test_author_accent_omission_preserves_full_name_match(pdf_file, expected_paper, candidate):
    expected = replace(expected_paper, authors=("Jeroen Beliën",))
    paper = pdf_file(author="Jeroen Belien")
    assert validate_artifact(paper, expected, candidate).status == "verified_fulltext"


def test_cover_doi_does_not_hide_supplement_label_on_article_page(pdf_file, expected_paper, candidate):
    paper = pdf_file(title="Supplementary material", front_matter=("Repository copy\ndoi:10.1234/queues",))
    assert validate_artifact(paper, expected_paper, candidate).reason_code == "supplementary_material"


def test_cover_doi_does_not_hide_accepted_version_label(pdf_file, expected_paper, candidate):
    paper = pdf_file(author="Jane Smith - Accepted Manuscript", front_matter=("Repository copy\ndoi:10.1234/queues",))
    assert validate_artifact(paper, expected_paper, replace(candidate, version="publishedVersion")).reason_code == "version_evidence_conflict"


@pytest.mark.parametrize("cover_doi", ["", "\ndoi:10.1234/queues"])
def test_correct_cover_cannot_override_wrong_main_article(pdf_file, expected_paper, candidate, cover_doi):
    paper = pdf_file(title="An Entirely Different Article", author="Other Researcher", front_matter=("University Repository\nCopyright 2024", "Queueing and Service Systems\nJane Smith\nRepository metadata record" + cover_doi))
    assert validate_artifact(paper, expected_paper, candidate).status == "ambiguous_match"


def test_catalogue_abstract_page_is_not_mistaken_for_article_front_page(pdf_file, expected_paper, candidate):
    paper = pdf_file(front_matter=("University Repository\nReport 2024-01", "REPORT SERIES\nABSTRACT AND KEYWORDS\nAbstract: Catalogue description.\nAvailability: repository"))
    assert validate_artifact(paper, expected_paper, candidate).status == "verified_fulltext"


def test_standalone_front_page_number_is_not_part_of_title(pdf_file, expected_paper, candidate):
    paper = pdf_file(title="1\nQueueing and Service Systems")
    assert validate_artifact(paper, expected_paper, candidate).status == "verified_fulltext"


def test_separately_encoded_cedilla_does_not_split_author_name(pdf_file, expected_paper, candidate):
    expected = replace(expected_paper, authors=("Tolga Bektaş",))
    paper = pdf_file(author="Tolga Bekta¸ s")
    assert validate_artifact(paper, expected, candidate).status == "verified_fulltext"


def test_raised_affiliation_marker_does_not_change_surname(pdf_file, expected_paper, candidate):
    paper = pdf_file(author_marker=("a", True))
    assert validate_artifact(paper, expected_paper, candidate).status == "verified_fulltext"


def test_baseline_surname_suffix_is_not_removed(pdf_file, expected_paper, candidate):
    paper = pdf_file(author_marker=("a", False))
    assert validate_artifact(paper, expected_paper, candidate).status == "ambiguous_match"


def test_affiliation_fallback_cannot_match_wrong_title(pdf_file, expected_paper, candidate):
    paper = pdf_file(title="A Comment on Queueing and Service Systems", author_marker=("a", True))
    assert validate_artifact(paper, expected_paper, candidate).status == "ambiguous_match"


def test_grips_running_header_is_separate_from_article_title(pdf_file, expected_paper, candidate):
    paper = pdf_file(title="G R I P S Policy Information Center Discussion Paper: 07-08\n1\nQueueing and Service Systems")
    assert validate_artifact(paper, expected_paper, candidate).status == "verified_fulltext"


def test_geometry_cannot_promote_body_citation_into_author_header(pdf_file, expected_paper, candidate):
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import DecodedStreamObject, NameObject
    paper = pdf_file(author="Other Researcher")
    writer = PdfWriter(clone_from=paper.path)
    page = writer.pages[0]
    stream = DecodedStreamObject()
    stream.set_data(page.get_contents().get_data() + b"\nBT /F1 10 Tf 340 710 Td (Prior work by Jane Smith is discussed below.) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    writer.write(paper.path)
    data = paper.path.read_bytes()
    paper = replace(paper, sha256=sha256(data).hexdigest(), byte_count=len(data))
    assert validate_artifact(paper, expected_paper, candidate).status == "ambiguous_match"


def test_matching_primary_arxiv_stamp_proves_identifier_with_wrapped_title(pdf_file, expected_paper, candidate):
    paper = replace(expected_paper, identifier_kind="arxiv", identifier="2401.01234v2")
    artifact = pdf_file(title="Published as a conference paper\nQueueing and Service Systems", body=["arXiv:2401.01234v2 [cs.LG] 12 Mar 2024"] + ["Full article body. " * 10] * 15)
    result = validate_artifact(artifact, paper, replace(candidate, paper_id=paper.paper_id, version="submittedVersion"))
    assert result.status == "verified_fulltext"
    assert result.identity_evidence == "primary_arxiv"


def test_arxiv_journal_doi_does_not_conflict_with_matching_platform_identifier(pdf_file, expected_paper, candidate):
    expected = replace(expected_paper, identifier_kind="arxiv", identifier="2401.01234v2")
    paper = pdf_file(author="Jane Smith\ndoi:10.1234/queues", body=["arXiv:2401.01234v2 [cs.LG] 12 Mar 2024"] + ["Full article body. " * 10] * 15)
    source = replace(candidate, paper_id=expected.paper_id, provider="arxiv", location_id="arxiv:2401.01234v2")
    assert validate_artifact(paper, expected, source).status == "verified_fulltext"


def test_arxiv_unversioned_input_must_match_pinned_candidate_version(pdf_file, expected_paper, candidate):
    expected = replace(expected_paper, identifier_kind="arxiv", identifier="2401.01234")
    paper = pdf_file(body=["arXiv:2401.01234v1 [cs.LG] 12 Mar 2024"] + ["Full article body. " * 10] * 15)
    source = replace(candidate, paper_id=expected.paper_id, provider="arxiv", location_id="arxiv:2401.01234v2", uri="https://arxiv.org/pdf/2401.01234v2")
    assert validate_artifact(paper, expected, source).reason_code == "primary_identifier_mismatch"


@pytest.mark.parametrize(("expected", "actual", "status"), [
    ("Raghuram Rajan", "Raghuram G. Rajan", "verified_fulltext"),
    ("Niels A.H. Agatz", "Niels Agatz", "verified_fulltext"),
    ("Jane A. Smith", "Jane B. Smith", "ambiguous_match"),
    ("Jane Smith", "Jane Other Smith", "ambiguous_match"),
])
def test_middle_initial_omission_preserves_name_conflicts(pdf_file, expected_paper, candidate, expected, actual, status):
    paper=replace(expected_paper,authors=(expected,))
    assert validate_artifact(pdf_file(author=actual),paper,candidate).status==status
