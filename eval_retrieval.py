"""Regression harness for the active bill's hierarchical retrieval behavior.

Run without arguments to evaluate the official Electoral Act PDF, or provide a
text/PDF path and title for another bill.
"""

import argparse
import time
from pathlib import Path

from src.retriever import ingest_file

ELECTORAL_TEST_CASES = [
    {"question": "How do I register to vote?", "expected_section": "Section 9"},
    {"question": "What documents can I use for voter registration?", "expected_section": "Section 10"},
    {"question": "How are election results transmitted?", "expected_section": "Section 60"},
    {"question": "How does the Act regulate Area Council elections?", "expected_section": "Section 102"},
    {"question": "What is the penalty for double registration?", "expected_section": "Section 12"},
    {"question": "Ta yaya zan yi rajistar zabe?", "expected_section": "Section 9"},
]

SAMPLE_TEST_CASES = [
    {"question": "What happens if a parent doesn't enrol their child in school?", "expected_section": "Section 7"},
    {"question": "How is the Board funded?", "expected_section": "Section 6"},
    {"question": "What is the penalty for non-compliance?", "expected_section": "Section 8"},
    {"question": "What law does this repeal?", "expected_section": "Section 10"},
]


def run_eval(filepath: str, title: str, test_cases, top_k: int = 3):
    retriever = ingest_file(filepath, title)

    hits = 0
    total_latency = 0.0

    for case in test_cases:
        start = time.time()
        results = retriever.query(case["question"], top_k=top_k)
        latency = time.time() - start
        total_latency += latency

        retrieved_sections = [chunk.section or "" for chunk, _ in results]
        hit = any(case["expected_section"] in s for s in retrieved_sections)
        hits += int(hit)

        status = "HIT" if hit else "MISS"
        print(f"[{status}] \"{case['question']}\" -> top match: {retrieved_sections[0] if retrieved_sections else 'none'} ({latency*1000:.1f}ms)")

    hit_rate = hits / len(test_cases)
    avg_latency = (total_latency / len(test_cases)) * 1000
    print(f"\nHit-rate@{top_k}: {hit_rate:.0%}  |  Avg latency: {avg_latency:.1f}ms")


def main():
    parser = argparse.ArgumentParser(description="Evaluate retrieval for a bill text or PDF.")
    default_path = Path("data/electoral_act_2026.pdf")
    parser.add_argument("filepath", nargs="?", default=str(default_path if default_path.exists() else "data/sample_bill.txt"))
    parser.add_argument("title", nargs="?", default="Electoral Act, 2026")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()
    cases = ELECTORAL_TEST_CASES if "electoral" in Path(args.filepath).stem.lower() else SAMPLE_TEST_CASES
    run_eval(args.filepath, args.title, cases, top_k=args.top_k)


if __name__ == "__main__":
    main()
