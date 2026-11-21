"""Turn an uploaded PDF / Word / text file into plain text the lecturer can teach from."""
import io

MAX_CHARS = 60000
MAX_BYTES = 15 * 1024 * 1024


def extract_text(filename: str, data: bytes) -> str:
    if len(data) > MAX_BYTES:
        raise ValueError("That file is larger than 15 MB. Please upload a smaller one.")
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValueError("PDF support needs the 'pypdf' package (pip install pypdf).") from exc
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
    elif name.endswith(".docx"):
        try:
            import docx
        except ImportError as exc:
            raise ValueError("Word support needs the 'python-docx' package (pip install python-docx).") from exc
        document = docx.Document(io.BytesIO(data))
        text = "\n".join(p.text for p in document.paragraphs)
    elif name.endswith((".txt", ".md", ".markdown", ".csv")):
        text = data.decode("utf-8", errors="replace")
    else:
        raise ValueError("Unsupported file type. Upload a PDF, Word (.docx), .txt or .md file.")
    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if len(text) < 80:
        raise ValueError("Could not find readable text in that file (scanned PDFs need OCR first).")
    return text[:MAX_CHARS]
