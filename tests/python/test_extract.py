import json
from hashlib import sha256

from paper_access.extract import extract_text
from paper_access.models import Artifact, AttemptOutcome


def test_pdf_extraction_retains_page_mapping_and_warns_about_layout(pdf_file, tmp_path):
    output = extract_text(pdf_file(), tmp_path / "text")
    data = json.loads(output.read_text())
    assert len(data["pages"]) == 2
    assert data["pages"][0]["page"] == 1
    assert "Queueing and Service Systems" in data["pages"][0]["text"]
    assert data["quality"] == "text_extracted_layout_unverified"


def test_html_script_content_is_not_extracted(tmp_path):
    path = tmp_path / "paper.html"
    path.write_text('<article><h1>A paper</h1><script>secret_script()</script><p>Actual body.</p></article>')
    data = path.read_bytes()
    output = extract_text(Artifact(path, sha256(data).hexdigest(), "text/html", len(data)), tmp_path / "text")
    text = output.read_text()
    assert "Actual body." in text and "secret_script" not in text


def test_html_text_outside_paragraph_tags_is_preserved(tmp_path):
    path = tmp_path / "paper.html"
    path.write_text('<article><h1>A paper</h1><h2>Introduction</h2><div>Unique full text inside a div.</div><table><tr><td>Table value 42</td></tr></table></article>')
    data = path.read_bytes()
    output = extract_text(Artifact(path, sha256(data).hexdigest(), "text/html", len(data)), tmp_path / "text")
    result = json.loads(output.read_text())
    assert "Unique full text inside a div." in result["text"]
    assert "Table value 42" in result["text"]
