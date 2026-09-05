"""Parse legislative text into legally meaningful hierarchical chunks."""

import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Chunk:
    id: str
    title: str
    part: Optional[str]
    section: Optional[str]
    text: str
    level: str = "section"
    subsection: Optional[str] = None
    parent_id: Optional[str] = None

    def citation(self) -> str:
        pieces = [p for p in [self.part, self.section] if p]
        citation = " > ".join(pieces) if pieces else self.title
        if self.subsection:
            citation = f"{citation} > {self.subsection}"
        return citation


PART_RE = re.compile(r"^PART\s+([IVXLCDM]+|\d+)(?:\s*[-:]\s*|\s+)(.+)$", re.IGNORECASE)
SECTION_RE = re.compile(r"^Section\s+(\d+)(?:\s*[-:.]\s*|\s+)(.+)$", re.IGNORECASE)
ACT_SECTION_RE = re.compile(r"^(\d{1,3})\s*[.\u2013\u2014?\-]+\s*(?:\((\d+[A-Za-z]?)\)\s*)?(.+)$")
SUBSECTION_RE = re.compile(r"^\((\d+[A-Za-z]?)\)\s*(.*)$")
PARAGRAPH_RE = re.compile(r"^\(([a-z])\)\s*(.*)$")


def parse_document(raw_text: str, doc_title: str = "Untitled Document") -> List[Chunk]:
    """
    Walk the document line by line, tracking the current Part and Section,
    and group all following text under that heading until the next heading.
    """
    lines = raw_text.splitlines()
    cleaned_lines = []
    skip_contents = False
    for line in lines:
        stripped = line.strip()
        normalized = " ".join(stripped.upper().split())
        if stripped.startswith("<PARSED TEXT FOR PAGE:") or stripped.startswith("<IMAGE FOR PAGE:"):
            continue
        if "ARRANGEMENT OF SECTIONS" in normalized:
            skip_contents = True
            continue
        if skip_contents and "ENACTED BY THE NATIONAL ASSEMBLY" in normalized:
            skip_contents = False
        if not skip_contents:
            cleaned_lines.append(line)
    lines = cleaned_lines

    chunks: List[Chunk] = []
    current_part: Optional[str] = None
    current_section: Optional[str] = None
    current_section_num: Optional[str] = None
    section_buffer: List[str] = []
    subsection_buffers: dict[str, List[str]] = {}
    subsection_order: List[str] = []
    in_appendix = False

    def append_chunk(text: str, level: str, subsection: Optional[str] = None, parent_id: Optional[str] = None):
        text = text.strip()
        if not text:
            return
        chunk_id = f"{current_section_num or 'header'}-{level}-{len(chunks)}"
        chunks.append(
            Chunk(
                id=chunk_id,
                title=doc_title,
                part=current_part,
                section=current_section,
                text=text,
                level=level,
                subsection=subsection,
                parent_id=parent_id,
            )
        )

    def flush_section():
        nonlocal section_buffer, subsection_buffers, subsection_order
        if not section_buffer or not current_section:
            section_buffer = []
            subsection_buffers = {}
            subsection_order = []
            return

        section_start = len(chunks)
        append_chunk("\n".join(section_buffer), "section")
        section_id = chunks[section_start].id
        for subsection in subsection_order:
            append_chunk(
                "\n".join(subsection_buffers[subsection]),
                "subsection",
                subsection=f"({subsection})",
                parent_id=section_id,
            )
        section_buffer = []
        subsection_buffers = {}
        subsection_order = []

    for line in lines:
        stripped = line.strip()
        part_match = PART_RE.match(stripped)
        section_match = SECTION_RE.match(stripped)
        act_section_match = ACT_SECTION_RE.match(stripped)
        subsection_match = SUBSECTION_RE.match(stripped)
        paragraph_match = PARAGRAPH_RE.match(stripped)

        appendix_heading = stripped.upper().startswith((
            "SCHEDULES",
            "FIRST SCHEDULE",
            "SECOND SCHEDULE",
            "THIRD SCHEDULE",
            "SUPPLEMENTAL TRANSITIONAL PROVISIONS",
        ))
        if appendix_heading:
            flush_section()
            in_appendix = True
            current_part = stripped.title()
            current_section = None
            current_section_num = None
            section_buffer.append(stripped)
            continue

        if part_match and not in_appendix:
            flush_section()
            current_part = f"Part {part_match.group(1)} - {part_match.group(2)}"
            current_section = None
            current_section_num = None
            continue

        if section_match and not in_appendix:
            flush_section()
            current_section_num = section_match.group(1)
            current_section = f"Section {current_section_num} - {section_match.group(2)}"
            continue

        if act_section_match and current_part and not in_appendix:
            flush_section()
            current_section_num = act_section_match.group(1)
            subsection = act_section_match.group(2)
            heading = act_section_match.group(3).strip()
            current_section = f"Section {current_section_num} - {heading}"
            section_buffer.append(stripped)
            if subsection:
                subsection_buffers[subsection] = [stripped]
                subsection_order.append(subsection)
            continue

        if subsection_match and current_section:
            subsection = subsection_match.group(1)
            if subsection not in subsection_buffers:
                subsection_buffers[subsection] = []
                subsection_order.append(subsection)
            subsection_buffers[subsection].append(stripped)
            section_buffer.append(line)
            continue

        if paragraph_match and subsection_order:
            section_buffer.append(line)
            subsection_buffers[subsection_order[-1]].append(stripped)
            continue

        section_buffer.append(line)
        if subsection_order:
            subsection_buffers[subsection_order[-1]].append(line)

    flush_section()
    return [chunk for chunk in chunks if chunk.text]


if __name__ == "__main__":
    with open("data/sample_bill.txt", "r", encoding="utf-8") as f:
        text = f.read()
    for c in parse_document(text, doc_title="Plateau State Basic Education (Amendment) Bill, 2026"):
        print(f"[{c.citation()}]")
        print(c.text[:120].replace("\n", " "), "...\n")
