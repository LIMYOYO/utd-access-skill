from hashlib import sha256

import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from paper_access.models import Artifact, Candidate, PaperInput, SourceRef


@pytest.fixture
def expected_paper():
    return PaperInput("doi", "10.1234/queues", (SourceRef("input.txt", 1, "10.1234/queues"),),
                      title="Queueing and Service Systems", authors=("Jane Smith",), year=2024)


@pytest.fixture
def candidate(expected_paper):
    return Candidate(expected_paper.paper_id, "repository", "repo:one", "https://repo.example/file.pdf",
                     version="acceptedVersion", version_evidence="repository metadata", license="cc-by")


@pytest.fixture
def pdf_file(tmp_path):
    def make(name="paper.pdf", title="Queueing and Service Systems", author="Jane Smith", body=None, front_matter=(), author_marker=None):
        writer = PdfWriter()
        paragraphs = [title, author, "Abstract", "We study queueing systems with heterogeneous customers.", "1 Introduction"]
        paragraphs.extend(body or ["Service capacity determines waiting times. We characterize the optimal allocation across queues."] * 30)
        chunks = [page.splitlines() for page in front_matter] + [paragraphs[offset:offset + 20] for offset in range(0, len(paragraphs), 20)]
        for chunk in chunks:
            page = writer.add_blank_page(width=612, height=792)
            font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica"), NameObject("/Encoding"): NameObject("/WinAnsiEncoding")})
            page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
            text = "BT /F1 10 Tf 30 740 Td 16 TL\n"
            for line in chunk:
                escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                if line == author and author_marker is not None:
                    marker, raised = author_marker
                    text += f"({escaped}) Tj /F1 {6 if raised else 10} Tf {4 if raised else 0} Ts ({marker}) Tj 0 Ts /F1 10 Tf T*\n"
                else:
                    text += f"({escaped}) Tj T*\n"
            stream = DecodedStreamObject()
            stream.set_data((text + "ET").encode("latin-1"))
            page[NameObject("/Contents")] = writer._add_object(stream)
        path = tmp_path / name
        writer.write(path)
        data = path.read_bytes()
        return Artifact(path, sha256(data).hexdigest(), "application/pdf", len(data))
    return make
