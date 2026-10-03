from pathlib import Path
import pytest
from paper_access.bridge.validation import stage_candidate, published_informs_evidence


def test_staging_rejects_symlinks_escape_nonpdf(tmp_path):
    root=tmp_path/'downloads';root.mkdir();stage=tmp_path/'stage';stage.mkdir()
    outside=tmp_path/'outside.pdf';outside.write_bytes(b'%PDF-1.4\nx')
    (root/'link.pdf').symlink_to(outside)
    for p in [outside,root/'link.pdf']:
        with pytest.raises(ValueError):stage_candidate(p,root,stage)
    f=root/'x.pdf';f.write_bytes(b'<html>login</html>')
    with pytest.raises(ValueError):stage_candidate(f,root,stage)
    f.write_bytes(b'%PDF-1.4\nx')
    assert stage_candidate(f,root,stage).read_bytes()==f.read_bytes()
    with pytest.raises(ValueError):stage_candidate(f,root,stage,max_bytes=3)


def test_version_requires_positive_evidence(tmp_path):
    from pypdf import PdfWriter
    f=tmp_path/'blank.pdf';w=PdfWriter();w.add_blank_page(100,100);w.write(f)
    assert published_informs_evidence(f,'10.1287/a') is None
