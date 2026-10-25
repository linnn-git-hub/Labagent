from typing import Dict, Any
from schemas import SummarizePDFArgs, SummarizePDFResult
import PyPDF2
import os


def summarize_pdf(args: Dict[str, Any]):
    """Summarize a local PDF file path. Returns summary and highlights."""
    # Accept either dict or already-parsed args
    if isinstance(args, dict):
        parsed = SummarizePDFArgs(**args)
    else:
        parsed = args

    path = parsed.path
    if not path or not os.path.exists(path):
        return {"error": "path missing or not found", "summary": ""}

    reader = PyPDF2.PdfReader(path)
    pages = parsed.pages or list(range(len(reader.pages)))
    texts = []
    for p in pages:
        if p < 0 or p >= len(reader.pages):
            continue
        page = reader.pages[p]
        try:
            texts.append(page.extract_text() or "")
        except Exception:
            texts.append("")

    full = "\n".join(texts)
    # naive summary: first N characters / sentences depending on length
    if parsed.summary_length == "short":
        summary = full[:1000]
    elif parsed.summary_length == "medium":
        summary = full[:3000]
    else:
        summary = full[:8000]

    # create simple highlights: first 3 non-empty lines
    highlights = [line.strip() for line in summary.splitlines() if line.strip()][:3]
    result = SummarizePDFResult(summary=summary, highlights=highlights, source_pages=pages)
    return result.dict()
