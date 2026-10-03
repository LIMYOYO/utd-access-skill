from pathlib import Path

import pytest

from paper_access.imports import import_records, normalize_identifier


@pytest.mark.parametrize(("value", "expected"), [
    ("https://doi.org/10.1287/MSOM.5.2.79.16071", ("doi", "10.1287/msom.5.2.79.16071")),
    ("doi:10.1007/BF00154886.", ("doi", "10.1007/bf00154886")),
    ("https://doi.org/10.1002/(SICI)1099-1234(199901)20:1%3C1::AID-X%3E3.0.CO;2-X", ("doi", "10.1002/(sici)1099-1234(199901)20:1<1::aid-x>3.0.co;2-x")),
    ("(10.1234/test(one)).", ("doi", "10.1234/test(one)")),
    ("10.2139/ssrn.4189586", ("ssrn", "4189586")),
    ("https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4189586", ("ssrn", "4189586")),
    ("https://arxiv.org/pdf/2301.12345v2", ("arxiv", "2301.12345v2")),
    ("arXiv:hep-th/9901001v1", ("arxiv", "hep-th/9901001v1")),
    ("https://www.nber.org/papers/w12345", ("nber", "w12345")),
    ("RePEc:nbr:nberwo:12345", ("repec", "RePEc:nbr:nberwo:12345")),
    ("10.123/nope", None),
    ("https://evil.test/?doi=10.1234/hidden", None),
])
def test_identifier_normalization(value, expected):
    assert normalize_identifier(value) == expected


def write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_text_deduplicates_but_preserves_input_lineage(tmp_path):
    path = write(tmp_path, "papers.txt", "10.1287/msom.5.2.79.16071\n\nhttps://doi.org/10.1287/MSOM.5.2.79.16071\n10.bad/broken\n10.2139/ssrn.4189586\nAn unresolved paper title\n")
    papers, issues = import_records(path)
    assert [p.identifier_kind for p in papers] == ["doi", "ssrn", "title"]
    assert [s.line for s in papers[0].sources] == [1, 3]
    assert papers[0].sources[1].raw == "https://doi.org/10.1287/MSOM.5.2.79.16071"
    assert papers[2].title == "An unresolved paper title"
    assert [(i.line, i.raw) for i in issues] == [(4, "10.bad/broken")]


def test_csv_metadata_unicode_and_invalid_row_recovery(tmp_path):
    path = write(tmp_path, "papers.csv", '\ufeffdoi,title,authors,year\n10.1234/one,"Title, with comma",张三; Smith,2024\nbad-id,Broken DOI,,2020\n,Title only,Another Author,2023\n10.1234/two,Second,,oops\n')
    papers, issues = import_records(path)
    assert len(papers) == 2
    assert papers[0].title == "Title, with comma"
    assert papers[0].authors == ("张三", "Smith")
    assert papers[0].year == 2024
    assert papers[1].identifier_kind == "title"
    assert [i.line for i in issues] == [3, 5]


def test_multiline_csv_source_line_is_first_physical_line(tmp_path):
    path = write(tmp_path, "multiline.csv", 'doi,title\n10.1234/one,"Line one\nline two"\n10.1234/two,Next\n')
    papers, issues = import_records(path)
    assert not issues
    assert [p.sources[0].line for p in papers] == [2, 4]


def test_bibtex_fields_and_broken_block_preserved(tmp_path):
    path = write(tmp_path, "papers.bib", '@article{one,\n title={A {Nested} Title}, doi={10.1234/one}, author={Smith, Jane and Doe, John}, year={2020}\n}\n@article{bad, doi={10.1234/bad}, doi={10.1234/other}}\n@article{two, title={Second title}}\n')
    papers, issues = import_records(path)
    assert len(papers) == 2
    assert papers[0].identifier == "10.1234/one"
    assert papers[0].authors == ("Smith, Jane", "Doe, John")
    assert papers[0].title == "A {Nested} Title"
    assert papers[1].sources[0].line == 5
    assert len(issues) == 1 and issues[0].line == 4
    assert "10.1234/bad" in issues[0].raw


def test_ris_bad_record_does_not_drop_next_valid_record(tmp_path):
    path = write(tmp_path, "papers.ris", 'TY  - JOUR\nDO  - 10.1234/one\nTI  - First\nAU  - Smith, Jane\nPY  - 2024/01/01\nER  - \nTY  - JOUR\nTI  - Missing end\nTY  - JOUR\nDO  - 10.1234/two\nTI  - Second\nER  - \n')
    papers, issues = import_records(path)
    assert [p.identifier for p in papers] == ["10.1234/one", "10.1234/two"]
    assert papers[0].year == 2024
    assert papers[1].sources[0].line == 9
    assert len(issues) == 1 and issues[0].line == 7


def test_same_title_without_identifier_is_not_automatically_merged(tmp_path):
    path = write(tmp_path, "papers.csv", 'title,authors\nShared title,Author A\nShared title,Author B\n')
    papers, _ = import_records(path)
    assert len(papers) == 2 and papers[0].paper_id != papers[1].paper_id


def test_unsupported_format_is_explicit(tmp_path):
    with pytest.raises(ValueError, match="format"):
        import_records(write(tmp_path, "papers.docx", "text"))


def test_malformed_url_is_an_issue_without_losing_later_inputs(tmp_path):
    path = write(tmp_path, "papers.txt", "https://[broken\n10.1234/valid\n")
    papers, issues = import_records(path)
    assert [p.identifier for p in papers] == ["10.1234/valid"]
    assert len(issues) == 1 and issues[0].raw == "https://[broken"


def test_csv_blank_lines_do_not_shift_source_line_numbers(tmp_path):
    path = write(tmp_path, "papers.csv", 'doi,title\n\n10.1234/one,"First\nsecond line"\n\n10.bad/nope,Invalid\n')
    papers, issues = import_records(path)
    assert papers[0].sources[0].line == 3
    assert papers[0].sources[0].raw == '10.1234/one,"First\nsecond line"'
    assert issues[0].line == 6
