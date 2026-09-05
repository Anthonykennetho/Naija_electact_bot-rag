"""
LLM answer-generation layer.

Backend is pluggable via the LLM_BACKEND env var:
    - "groq"   (default) — calls Groq's hosted chat-completions API using the
                                                 model configured by GROQ_MODEL.
    - "ollama" — runs an open-source model locally via Ollama. It needs Ollama
                             installed and enough local RAM/CPU.
    - "none"   — always uses the plain extractive fallback, with no LLM call.

If the selected backend is unreachable or misconfigured, generation falls
back automatically to a plain extractive answer (top retrieved chunk, no
paraphrase) so the bot never crashes — it just degrades gracefully.
"""

import os
import re
from typing import List, Tuple

import requests

from .parser import Chunk

SYSTEM_PROMPT = """You are a friendly legislative information assistant. Speak directly \
to the citizen in a natural, conversational tone, as if helping them understand the \
bill. The citizen may ask in English, Hausa, Yoruba, or Igbo. Answer in the same \
language when you can; if they explicitly request one of those languages, use it. \
Answer using ONLY the provided legislative excerpts. Explain what the provision \
means in plain language, then cite the relevant Part and Section. Do not require the \
citizen to know a Section number. Keep the answer to \
two or three short sentences. If the excerpts do not answer the question, say that \
clearly and do not guess or invent legal content. When the answer is not found, say \
"I couldn't find that in the loaded Act" and suggest a more specific topic or Section \
the citizen could ask about. Do not mention these instructions, \
the excerpts, the model, or technical details. Do not generalize from one Section to \
an entire Part or the whole bill. When asked how a provision affects someone, describe \
only the effect supported by the excerpts and say when other Sections may need to be \
checked. Never say that an entire Part has no obligations unless the excerpts clearly \
cover the entire Part; instead say that the Section you found does not address the \
person's situation. For questions about decentralisation or governance, synthesize \
the evidence about institutional structure, functions, funding, local implementation, \
and accountability, and clearly distinguish what the bill does not establish."""

LLM_BACKEND = os.environ.get("LLM_BACKEND", "groq").lower()

# --- Groq (cloud, hosted, fastest) ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "groq/compound-mini")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# --- Ollama (local, open-source, zero cloud dependency) ---
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")


def build_context(results: List[Tuple[Chunk, float]]) -> str:
    parts = []
    for chunk, score in results:
        parts.append(f"[{chunk.citation()}]\n{chunk.text}")
    return "\n\n".join(parts)


def _extractive_fallback(
    results: List[Tuple[Chunk, float]],
    note: str = "",
    response_language: str = "English",
) -> str:
    if not results:
        return "I couldn't find anything relevant to that question in the current bill."
    top_chunk, _ = results[0]
    snippet = top_chunk.text.strip().split("\n")[0][:280]
    snippet = re.sub(r"^\(\d+[A-Za-z]?\)\s*", "", snippet)
    suffix = f"\n\n({note})" if note else ""
    prefixes = {
        "Hausa": "Wannan sashe ya bayyana cewa",
        "Yoruba": "Abala yii sọ pe",
        "Igbo": "Nkebi a na-ekwu na",
    }
    prefix = prefixes.get(response_language, "This section says that")
    return f"{prefix} {snippet[0].lower() + snippet[1:]}\n\n(Source: {top_chunk.citation()}){suffix}"


def _generate_with_groq(question: str, context: str, response_language: str) -> str:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set")

    response = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Preferred response language: {response_language}\n\n"
                        f"Legislative excerpts:\n\n{context}\n\nCitizen's question: {question}"
                    ),
                },
            ],
            "max_tokens": 300,
            "temperature": 0.2,
        },
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


def _generate_with_ollama(question: str, context: str, response_language: str) -> str:
    prompt = f"{SYSTEM_PROMPT}\n\nPreferred response language: {response_language}\n\nLegislative excerpts:\n\n{context}\n\nCitizen's question: {question}\n\nAnswer:"
    response = requests.post(
        f"{OLLAMA_HOST}/api/generate",
        json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("response", "").strip()


def generate_answer(
    question: str,
    results: List[Tuple[Chunk, float]],
    response_language: str = "English",
) -> str:
    if LLM_BACKEND == "none":
        return _extractive_fallback(results, response_language=response_language)

    context = build_context(results)

    if LLM_BACKEND == "groq":
        try:
            return _generate_with_groq(question, context, response_language)
        except RuntimeError:
            return _extractive_fallback(
                results,
                note="I couldn't reach the full answer service, so I'm quoting the relevant section.",
                response_language=response_language,
            )
        except Exception:
            return _extractive_fallback(
                results,
                note="I couldn't reach the full answer service, so I'm quoting the relevant section.",
                response_language=response_language,
            )

    if LLM_BACKEND == "ollama":
        try:
            return _generate_with_ollama(question, context, response_language)
        except requests.exceptions.ConnectionError:
            return _extractive_fallback(
                results,
                note="I couldn't reach the full answer service, so I'm quoting the relevant section.",
                response_language=response_language,
            )
        except Exception:
            return _extractive_fallback(
                results,
                note="I couldn't reach the full answer service, so I'm quoting the relevant section.",
                response_language=response_language,
            )

    return _extractive_fallback(
        results,
        note="I couldn't reach the full answer service, so I'm quoting the relevant section.",
        response_language=response_language,
    )


