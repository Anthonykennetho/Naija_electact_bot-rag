"""Ingest a legislative text or PDF file into the retrieval index.

Usage:
    python ingest.py                     # ingests the synthetic sample bill
    python ingest.py path/to/bill.txt "Bill Title"
    python ingest.py path/to/bill.pdf "Bill Title"

The generated index is shared by the Telegram bot. Re-run ingestion whenever
the active bill changes, before starting bot.py.
"""

import sys
from pathlib import Path

from src.retriever import ingest_file


def _title_for(path: Path) -> str:
    return path.stem.replace("_", " ").replace("-", " ").strip().title()


def main():
    if len(sys.argv) >= 2:
        filepath = Path(sys.argv[1])
        title = sys.argv[2] if len(sys.argv) >= 3 else _title_for(filepath)
    else:
        filepath = Path("data/sample_bill.txt")
        title = "Plateau State Basic Education (Amendment) Bill, 2026"

    print(f"Ingesting: {filepath} ({title})")
    retriever = ingest_file(str(filepath), title or _title_for(filepath))
    retriever.save()
    sections = sum(chunk.level == "section" for chunk in retriever.chunks)
    subsections = sum(chunk.level == "subsection" for chunk in retriever.chunks)
    print(
        f"Indexed {len(retriever.chunks)} chunks ({sections} sections, "
        f"{subsections} subsections) -> index/tfidf_index.pkl"
    )


if __name__ == "__main__":
    main()
