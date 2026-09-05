"""Lightweight hierarchical legislative retrieval using TF-IDF and cosine similarity.

The index supports plain text and selectable-text PDFs, preserves Part,
Section, and subsection metadata, and reranks results for section-title
relevance and cross-section governance questions.
"""

import pickle
from pathlib import Path
from typing import List, Tuple

import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .parser import Chunk, parse_document

INDEX_PATH = Path(__file__).parent.parent / "index" / "tfidf_index.pkl"

_SUFFIXES = ("ing", "ed", "es", "s")


def _naive_stem(word: str) -> str:
    """
    Very lightweight suffix-stripping stemmer (no nltk dependency).
    Good enough to match "penalty"/"penalties" style variance without
    pulling in a heavier NLP stack. Not linguistically rigorous — swap
    for a real stemmer/lemmatizer if precision needs improve.
    """
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    for suf in _SUFFIXES:
        if word.endswith(suf) and len(word) - len(suf) > 2:
            return word[: -len(suf)]
    return word


_TOKEN_RE = re.compile(r"[a-zA-Z]+")


def _stemming_tokenizer(text: str):
    return [_naive_stem(tok.lower()) for tok in _TOKEN_RE.findall(text)]


def _expand_query(question: str) -> str:
    terms = question.lower()
    expansions = []
    if any(term in terms for term in ("decentral", "local government", "governance", "who does what")):
        expansions.extend(("Board", "functions", "funding", "implementation", "Local Government Areas", "monitoring", "standards"))
    if any(term in terms for term in ("fund", "budget", "grant", "finance", "money")):
        expansions.extend(("funding", "budgetary allocation", "grants", "contributions", "sources"))
    if any(term in terms for term in ("register to vote", "registration", "voter", "voters", "voting eligibility")):
        expansions.extend(("National Register of Voters", "continuous registration", "registration centre", "qualified", "citizen", "18 years", "NIN", "passport", "birth certificate"))
    if any(term in terms for term in ("area council", "local government election", "councillor", "chairman election")):
        expansions.extend(("Area Council", "Chairman", "Vice-Chairman", "Councillor", "Electoral Ward", "nomination", "voting", "election date"))
    if any(term in terms for term in ("rajistar", "zabe", "masu zaɓe", "katin zaɓe", "zaɓe")):
        expansions.extend(("voter registration", "National Register of Voters", "registration", "voter card", "qualified", "citizen"))
    if any(term in terms for term in ("ìdìbò", "idibo", "olùdìbò", "oludibo", "dìbò", "dibo")):
        expansions.extend(("voter registration", "election", "voting", "voter card", "polling unit"))
    if any(term in terms for term in ("ntuli aka", "ndebanye", "debanye aha", "onye votu", "ntuli")):
        expansions.extend(("voter registration", "election", "voting", "voter card", "polling unit"))
    return f"{question} {' '.join(expansions)}".strip()


class Retriever:
    def __init__(self):
        self.vectorizer: TfidfVectorizer | None = None
        self.matrix = None
        self.chunks: List[Chunk] = []

    def build(self, chunks: List[Chunk]):
        self.chunks = chunks
        # Prepend the section heading to the indexed text: headings often
        # carry the exact term a citizen searches for (e.g. "Penalties")
        # even when the body text uses different wording (e.g. "fine").
        corpus = [f"{c.citation()}. {c.text}" for c in chunks]
        self.vectorizer = TfidfVectorizer(
            tokenizer=_stemming_tokenizer,
            ngram_range=(1, 2),
            token_pattern=None,
        )
        self.matrix = self.vectorizer.fit_transform(corpus)

    def save(self, path: Path = INDEX_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({"vectorizer": self.vectorizer, "matrix": self.matrix, "chunks": self.chunks}, f)

    def load(self, path: Path = INDEX_PATH):
        with open(path, "rb") as f:
            data = pickle.load(f)
        self.vectorizer = data["vectorizer"]
        self.matrix = data["matrix"]
        self.chunks = data["chunks"]

    def query(self, question: str, top_k: int = 3) -> List[Tuple[Chunk, float]]:
        if self.vectorizer is None:
            raise RuntimeError("Retriever index not loaded. Run ingest.py first.")
        retrieval_question = _expand_query(question)
        q_vec = self.vectorizer.transform([retrieval_question])
        sims = cosine_similarity(q_vec, self.matrix)[0]
        query_terms = set(_stemming_tokenizer(retrieval_question))
        ranked = []
        for chunk, similarity in zip(self.chunks, sims):
            heading_terms = set(_stemming_tokenizer(f"{chunk.part or ''} {chunk.section or ''}"))
            heading_overlap = len(query_terms & heading_terms)
            score = float(similarity) + min(heading_overlap, 2) * 0.08
            ranked.append((chunk, score))
        ranked.sort(key=lambda x: x[1], reverse=True)
        diverse = []
        seen_sections = set()
        for chunk, score in ranked:
            section_key = (chunk.title, chunk.section or chunk.id)
            if section_key in seen_sections:
                continue
            seen_sections.add(section_key)
            diverse.append((chunk, score))
            if len(diverse) == top_k:
                break
        return diverse


def ingest_file(filepath: str, doc_title: str) -> Retriever:
    source = Path(filepath)
    if source.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("PDF ingestion requires pypdf. Run `pip install pypdf`.") from exc
        reader = PdfReader(str(source))
        raw = "\n\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        with open(source, "r", encoding="utf-8") as f:
            raw = f.read()

    if not raw.strip():
        raise ValueError(f"No text could be extracted from {source}")
    chunks = parse_document(raw, doc_title=doc_title)
    if not chunks:
        raise ValueError(
            "No legal sections were detected. Check the source formatting or extend "
            "the heading patterns in src/parser.py."
        )
    retriever = Retriever()
    retriever.build(chunks)
    return retriever
