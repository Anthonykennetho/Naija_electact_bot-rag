# Legislative Q&A Telegram Bot — Demo / Proof of Concept

A working end-to-end legislative RAG chatbot for making Nigerian legislation
easier to search and understand through Telegram.

## What this demonstrates

| Job requirement | Where it lives |
|---|---|
| Chatbot engine integration | `bot.py` (Telegram, via `python-telegram-bot`) |
| Generative AI / RAG-based apps | `src/retriever.py` (hierarchical retrieval) + `src/llm.py` (Groq by default, Ollama optional) |
| Legislative data ingestion & structuring | `ingest.py` + `src/parser.py` (Part → Section → subsection parsing for TXT/PDF and Nigerian Act numbering) |
| Low-bandwidth / basic-phone optimization | Plain-text-only replies, `MAX_REPLY_CHARS` cap in `bot.py`, lightweight TF-IDF retrieval (no large embedding model download) |
| Voice-note input / TTS pilot | `src/tts_stub.py` — integration point + notes, not wired into the default flow |
| QA ahead of launch | `eval_retrieval.py` — retrieval hit-rate/latency harness |

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env        # fill in TELEGRAM_BOT_TOKEN at minimum

python ingest.py data/electoral_act_2026.pdf "Electoral Act, 2026"
python bot.py               # starts polling — message the bot on Telegram
```

On Windows PowerShell, use the project interpreter:

```powershell
.\venv\Scripts\python.exe ingest.py data\electoral_act_2026.pdf "Electoral Act, 2026"
.\venv\Scripts\python.exe bot.py
```

To ingest a real bill, provide a plain-text file or a PDF with selectable text:

```bash
python ingest.py data/plateau_education_bill.pdf "Plateau Education Bill 2026"
python eval_retrieval.py
python bot.py
```

The parser creates full Section chunks and smaller subsection chunks. Retrieval
keeps distinct Sections in the answer context, which helps cross-cutting questions
such as decentralisation combine provisions about the Board, funding, local
implementation, and accountability. Scanned/image-only PDFs need OCR first;
`pypdf` extracts selectable text but does not perform OCR.

For a Nigerian Act such as the Electoral Act, 2026, the parser also accepts
numbered provisions such as `1.—(1)` and headings written as `PART I — ...`.
Save the parsed text as `data/electoral_act_2026.txt`, or use the original
selectable PDF directly:

```bash
python ingest.py data/electoral_act_2026.txt "Electoral Act, 2026"
# or:
python ingest.py data/electoral_act_2026.pdf "Electoral Act, 2026"
python bot.py
```

Getting a `TELEGRAM_BOT_TOKEN`: message **@BotFather** on Telegram, send
`/newbot`, follow the prompts, and it will hand you a token.

### Enabling full LLM-generated answers (Groq — hosted, fastest, no local compute)

By default the bot uses **Groq**, which runs fully open-source models
(Llama 3.1/3.3) on inference hardware built specifically for low latency —
typically a few hundred milliseconds per response. It's a plain HTTP API
call, so it puts **zero load on your laptop** — safe for any machine,
unlike running a model locally.

```bash
# 1. Create a free account and API key: https://console.groq.com/keys
# 2. Add it to your .env file:
#    GROQ_API_KEY=gsk_your_key_here
```

That's it — no local model download is required. If the key is
missing or the request fails for any reason, the bot **does not crash** —
it falls back to a plain extractive answer from the most relevant Section
without exposing provider diagnostics. This graceful degradation
matters for a production chatbot: a citizen should never see a raw error.

### Alternative: fully local, zero-cloud option (Ollama)

If you'd rather run a model entirely on your own machine with no internet
dependency (and your laptop can handle it), set `LLM_BACKEND=ollama` in
`.env`, install Ollama from ollama.com, run `ollama serve`, and
`ollama pull llama3.2:1b`. Small models like this run on CPU without a GPU,
but still use noticeably more RAM/CPU than the Groq option — Groq is the
lighter-weight choice if you're unsure your machine can handle local
inference comfortably.

To swap models or backends, just change `LLM_BACKEND` / `GROQ_MODEL` /
`OLLAMA_MODEL` in `.env` — no code changes needed, since the LLM backend is
intentionally decoupled from the retrieval logic.

## Sample data

`data/sample_bill.txt` is a **synthetic** sample bill for regression tests; it
is not a real, currently-in-force law. The active official source in this
workspace is the National Assembly's Electoral Act PDF:
`https://nass.gov.ng/documents/download/11248`. The parser accepts
common `PART I -`, `PART I:`, `SECTION 1 -`, `SECTION 1:`, and `SECTION 1.`
heading forms, plus numbered provisions such as `1.—(1)` in Nigerian Acts.

## Architecture notes

- **Retrieval**: TF-IDF + cosine similarity, not a heavy embedding model.
  This was a deliberate low-bandwidth/cost trade-off for a small corpus —
  swap in a real vector DB (Chroma, FAISS, Pinecone) once the corpus grows
  past a handful of bills, since TF-IDF's lexical matching will degrade on
  paraphrased or vague questions that share few literal words with the text.
- **Chunking**: hierarchical (Part → Section → subsection), not fixed-size
  windows. Full Sections support broad questions; subsection chunks support
  precise duties and penalties. Section diversity prevents parent/child
  duplicates from crowding out distinct evidence.
- **Stemming**: a small custom suffix-stripping stemmer is used instead of
  nltk, to avoid a corpus-download dependency for a lightweight demo. Swap
  for a real stemmer/lemmatizer if precision needs improve at scale.

## Process overview

1. **Acquire**: place a real `.txt` or selectable-text `.pdf` in `data/`.
2. **Ingest**: `ingest.py` extracts text and writes `index/tfidf_index.pkl`.
3. **Parse**: `parser.py` removes PDF page markers/TOC content and builds
  Part, Section, and subsection chunks.
4. **Retrieve**: `retriever.py` expands common citizen wording, ranks with
  TF-IDF plus heading relevance, and keeps distinct Sections in context.
5. **Answer**: `llm.py` generates a short grounded explanation with citations;
  it falls back to an extractive response if the LLM is unavailable.
6. **Deliver**: `bot.py` handles `/start`, `/help`, and Telegram questions.

To change the active bill, rerun ingestion before restarting the bot. Only one
Telegram polling process should run for the configured bot token.

## Porting to WhatsApp

The retrieval/LLM core (`src/retriever.py`, `src/llm.py`) is transport-agnostic
— it has no Telegram-specific code. To port to WhatsApp:

1. Register a Meta WhatsApp Business Cloud API app (or use Twilio's WhatsApp API).
2. Replace `bot.py`'s Telegram handlers with a webhook endpoint (e.g. FastAPI)
   that receives WhatsApp messages and calls the same `retriever.query()` +
   `generate_answer()` functions.
3. Reuse the same `MAX_REPLY_CHARS` low-bandwidth discipline.

## Publishing this on GitHub with a real, running bot

This repo is ready to push as-is — `.gitignore` already excludes `.env`
and the generated `index/` folder, so no secrets or build artifacts get
committed.

```bash
git init
git add .
git commit -m "Legislative Q&A Telegram bot demo"
git branch -M main
git remote add origin https://github.com/<your-username>/<repo-name>.git
git push -u origin main
```

A public GitHub repo alone doesn't make the bot *live*, though — Telegram
bots need a process running continuously to respond to messages. Your
laptop being on isn't a real solution for a demo you want to point people
to. To keep it actually running 24/7:

### Deploy to Railway (recommended — simplest path)

1. Go to railway.app, sign in with GitHub, click "New Project" → "Deploy from GitHub repo" → select this repo.
2. Railway auto-detects `Procfile` and runs `start.sh` as a background worker.
3. In the project's Variables tab, add: `TELEGRAM_BOT_TOKEN`, `LLM_BACKEND=groq`, `GROQ_API_KEY`.
4. Deploy. Check the logs for `"Bot starting (polling...)"` — if you see that with no errors, message your bot on Telegram and it will respond live, running on Railway's servers, not your laptop.

Railway's free tier includes a monthly usage credit, which is normally
enough to keep a small bot like this running continuously — check their
current pricing page for exact limits, since these change over time.

### Alternative: Render, Fly.io

Any platform that supports a persistent background worker (not just a
web server that sleeps when idle) works the same way: point it at this
repo, set it to run `bash start.sh`, add the same three environment
variables. Render and Fly.io both support this; check each platform's
current free-tier terms before relying on it for anything beyond a demo.


## Known limitations (honest, not hidden)

- TF-IDF retrieval will miss paraphrased questions that don't share
  vocabulary with the source text.
- The custom stemmer is intentionally naive (suffix-stripping only).
- `src/tts_stub.py` is an integration stub, not a working TTS pipeline —
  wiring it up needs a real ElevenLabs (or alternative) API key and testing.
- Real PDFs must contain selectable text; scanned bills need OCR first.
- Retrieval quality should be evaluated with questions specific to each new
  bill before deployment.
