from pathlib import Path
import re

from docx import Document
from pypdf import PdfReader


def clean_text(text: str) -> str:
    """
    Cleans the extracted text by removing extra whitespace and newlines.

    """
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    text = re.sub(r"[ \t]+", " ", text)

    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.split()


def extract_pdf_text(file_path: Path) -> str:
    """
    Extracts text from a PDF file.

    """

    reader = PdfReader(file_path)

    pages = []

    for page in reader.pages:
        text = page.extract_text()

        if text:
            pages.append(text)

    return clean_text("\n".join(pages))


def extract_docx_text(file_path: Path) -> str:
    """
    Extracts text from a DOCX file.

    """
    document = Document(file_path)

    paragraphs = []

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()

        if text:
            paragraphs.append(text)

    return clean_text("\n".join(paragraphs))


def extract_resume_text(file_path: Path) -> str:
    """
    Extracts text from a resume file (PDF or DOCX).

    """

    extension = Path(file_path).suffix.lower()

    if extension == ".pdf":
        return extract_pdf_text(file_path)

    if extension == ".docx":
        return extract_docx_text(file_path)

    raise ValueError(f"Unsupported file format: {extension}")
