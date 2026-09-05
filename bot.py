"""Telegram transport for the legislative RAG assistant.

Startup expects a previously built ``index/tfidf_index.pkl`` and loads
configuration from ``.env``. Rebuild the index with ``ingest.py`` whenever the
bill source changes, then run this module to start Telegram polling.
"""

import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from src.retriever import Retriever

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.request").setLevel(logging.WARNING)

load_dotenv(override=True)

MAX_REPLY_CHARS = 800  # keep responses short/cheap for low-bandwidth users

retriever = Retriever()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to State Bill Assistant.\n\n"
        "Ask one clear question about the loaded law in plain language. I will "
        "search the text and reply with the relevant Part and Section.\n\n"
        "Try:\n"
        "• How do I register to vote?\n"
        "• How are election results transmitted?\n"
        "• What happens if someone votes more than once?\n\n"
        "Commands:\n"
        "/help - see how to ask questions\n"
        "/topics - see example topics you can search"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "How to use me:\n"
        "1. Type your question normally.\n"
        "2. Mention the topic or Section if you know it.\n"
        "3. I will explain the answer in plain language and cite the source.\n\n"
        "Examples:\n"
        "• What documents do I need to register?\n"
        "• What is the penalty for double registration?\n"
        "• Who supervises Area Council elections?\n\n"
        "Use /topics for more examples. Use /start to see the welcome message. "
        "This bot provides information "
        "from the loaded law, not personal legal advice."
    )


async def topics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "You can ask about:\n\n"
        "Voter registration\n"
        "• What documents do I need to register to vote?\n"
        "• Who is qualified to register?\n"
        "• Can I transfer my voter registration?\n\n"
        "Voting and results\n"
        "• How are election results transmitted?\n"
        "• Where can I vote?\n"
        "• What happens if there is an emergency during an election?\n\n"
        "Offences and penalties\n"
        "• What is the penalty for double registration?\n"
        "• What is the penalty for bribery?\n"
        "• What happens if someone uses another person's voter card?\n\n"
        "Area Council elections\n"
        "• Who supervises Area Council elections?\n"
        "• How is an Area Council Chairman elected?\n"
        "• How can an Area Council member be recalled?\n\n"
        "Tip: include the topic or Section number in follow-up questions."
    )


async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = update.message.text.strip()
    if not question:
        return

    from src.llm import generate_answer  # local import keeps startup fast

    results = retriever.query(question, top_k=5)
    answer = generate_answer(question, results)

    if len(answer) > MAX_REPLY_CHARS:
        answer = answer[:MAX_REPLY_CHARS].rsplit(" ", 1)[0] + "…"

    await update.message.reply_text(answer)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Unhandled bot error", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "I couldn't process that request right now. Please try again shortly."
        )


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit(
            "Missing TELEGRAM_BOT_TOKEN. Get one from @BotFather on Telegram, "
            "then: export TELEGRAM_BOT_TOKEN='your-token-here'"
        )

    try:
        retriever.load()
    except FileNotFoundError:
        raise SystemExit("No index found. Run `python ingest.py` first.")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("topics", topics_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question))
    app.add_error_handler(error_handler)

    logger.info("Bot starting (polling)...")
    app.run_polling()


if __name__ == "__main__":
    main()
