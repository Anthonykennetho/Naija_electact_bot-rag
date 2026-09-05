"""Regression harness for the synthetic sample bill's retrieval behavior.

Extend ``TEST_CASES`` with questions for each newly ingested real bill before
deploying it. This script intentionally evaluates the sample corpus only.
"""

import time

from src.retriever import ingest_file

TEST_CASES = [
    {"question": "What happens if a parent doesn't enrol their child in school?", "expected_section": "Section 7"},
    {"question": "How is the Board funded?", "expected_section": "Section 6"},
    {"question": "What is the penalty for non-compliance?", "expected_section": "Section 8"},
    {"question": "What law does this repeal?", "expected_section": "Section 10"},
]


def run_eval(top_k: int = 3):
    retriever = ingest_file("data/sample_bill.txt", "Plateau State Basic Education (Amendment) Bill, 2026")

    hits = 0
    total_latency = 0.0

    for case in TEST_CASES:
        start = time.time()
        results = retriever.query(case["question"], top_k=top_k)
        latency = time.time() - start
        total_latency += latency

        retrieved_sections = [chunk.section or "" for chunk, _ in results]
        hit = any(case["expected_section"] in s for s in retrieved_sections)
        hits += int(hit)

        status = "HIT" if hit else "MISS"
        print(f"[{status}] \"{case['question']}\" -> top match: {retrieved_sections[0] if retrieved_sections else 'none'} ({latency*1000:.1f}ms)")

    hit_rate = hits / len(TEST_CASES)
    avg_latency = (total_latency / len(TEST_CASES)) * 1000
    print(f"\nHit-rate@{top_k}: {hit_rate:.0%}  |  Avg latency: {avg_latency:.1f}ms")


if __name__ == "__main__":
    run_eval()
