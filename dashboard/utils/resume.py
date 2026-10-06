"""utils/resume.py: read the text out of an uploaded resume.

Supports PDF, DOCX and TXT. Everything happens in memory for the current
session only; nothing is written to disk or sent anywhere. Limits keep a
bad or huge file from slowing the app down.
"""

import io

MAX_BYTES = 5 * 1024 * 1024
MAX_PDF_PAGES = 15
MAX_CHARS = 60_000
ALLOWED_TYPES = ["pdf", "docx", "txt"]


class ResumeReadError(Exception):
    """Raised with a message that is safe to show to the user."""


def _read_pdf(data):
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        raise ResumeReadError("That PDF is password protected. Remove the password or paste the text instead.")
    pages = reader.pages[:MAX_PDF_PAGES]
    return "\n".join((page.extract_text() or "") for page in pages)


def _read_docx(data):
    from docx import Document

    doc = Document(io.BytesIO(data))
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            parts.extend(cell.text for cell in row.cells)
    return "\n".join(parts)


def extract_resume_text(filename, data):
    """Return plain text from an uploaded file, or raise ResumeReadError."""
    if len(data) > MAX_BYTES:
        raise ResumeReadError("That file is larger than 5 MB. Try a shorter version or paste the text.")
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    try:
        if ext == "pdf":
            text = _read_pdf(data)
        elif ext == "docx":
            text = _read_docx(data)
        elif ext == "txt":
            text = data.decode("utf-8", errors="ignore")
        else:
            raise ResumeReadError("Upload a PDF, DOCX or TXT file.")
    except ResumeReadError:
        raise
    except Exception:
        raise ResumeReadError("We could not read that file. Try another copy or paste the text instead.")
    text = text.strip()
    if not text:
        raise ResumeReadError(
            "No text found in that file. Scanned resumes saved as images cannot be read, so paste the text instead."
        )
    return text[:MAX_CHARS]


def resume_uploader(label, text_key, uploader_key):
    """Streamlit file uploader that fills the text area stored under
    `text_key` with the resume text. Imported lazily so the parsing code
    above stays testable without Streamlit."""
    import streamlit as st

    def _on_upload():
        f = st.session_state.get(uploader_key)
        if f is None:
            st.session_state.pop(uploader_key + "_error", None)
            return
        try:
            st.session_state[text_key] = extract_resume_text(f.name, f.getvalue())
            st.session_state.pop(uploader_key + "_error", None)
            st.session_state[uploader_key + "_name"] = f.name
        except ResumeReadError as exc:
            st.session_state[uploader_key + "_error"] = str(exc)

    st.file_uploader(label, type=ALLOWED_TYPES, key=uploader_key, on_change=_on_upload,
                     help="PDF, DOCX or TXT, up to 5 MB. Read in your browser session only and never stored.")
    err = st.session_state.get(uploader_key + "_error")
    if err:
        st.warning(err)
    elif st.session_state.get(uploader_key) is not None and st.session_state.get(uploader_key + "_name"):
        st.caption(f"Loaded {st.session_state[uploader_key + '_name']}. You can edit the text below before checking.")
