"""Telegram transport for the legislative RAG assistant.

Startup expects a previously built ``index/tfidf_index.pkl`` and loads
configuration from ``.env``. Rebuild the index with ``ingest.py`` whenever the
bill source changes, then run this module to start Telegram polling.
"""

import logging
import os

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from src.retriever import Retriever

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.request").setLevel(logging.WARNING)

load_dotenv(override=True)

MAX_REPLY_CHARS = 800  # keep responses short/cheap for low-bandwidth users

retriever = Retriever()
user_languages: dict[int, str] = {}


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("English", callback_data="language:English"),
                InlineKeyboardButton("Hausa", callback_data="language:Hausa"),
            ],
            [
                InlineKeyboardButton("Yoruba", callback_data="language:Yoruba"),
                InlineKeyboardButton("Igbo", callback_data="language:Igbo"),
            ],
        ]
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to State Bill Assistant.\n\n"
        "Ask any clear question about the loaded law in your own words. You do "
        "not need to know a Section number.\n\n"
        "Try:\n"
        "• How do I register to vote?\n"
        "• How are election results transmitted?\n"
        "• What happens if someone votes more than once?\n\n"
        "Commands:\n"
        "/help - see how to ask questions\n"
        "/topics - see example topics you can search\n"
        "/languages - choose your response language"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "How to use me:\n"
        "1. Type your question normally; no legal wording is required.\n"
        "2. Tell me the topic, such as registration, voting, or penalties.\n"
        "3. I will explain the answer simply and cite the source.\n\n"
        "Examples:\n"
        "• What documents do I need to register?\n"
        "• What is the penalty for double registration?\n"
        "• Who supervises Area Council elections?\n\n"
        "Use /topics for more examples. Use /languages for language options. "
        "Use /start to see the welcome message. "
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
        "Tip: ask in your own words. You do not need to know the Section number."
    )


async def languages_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Choose the language you want me to use for my replies.\n\n"
        "This is a language choice, not a declaration of tribe. You can change it "
        "any time with /languages.",
        reply_markup=language_keyboard(),
    )


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    language = query.data.split(":", 1)[1]
    user_languages[query.from_user.id] = language
    await query.edit_message_text(
        f"Your reply language is now {language}. Ask your question in your own words."
    )


async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = update.message.text.strip()
    if not question:
        return

    from src.llm import generate_answer  # local import keeps startup fast

    results = retriever.query(question, top_k=5)
    language = user_languages.get(update.effective_user.id, "English")
    answer = generate_answer(question, results, response_language=language)

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
            "then add it to .env or your deployment service variables."
        )

    try:
        retriever.load()
    except FileNotFoundError:
        raise SystemExit("No index found. Run `python ingest.py` first.")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("topics", topics_command))
    app.add_handler(CommandHandler("languages", languages_command))
    app.add_handler(CallbackQueryHandler(language_callback, pattern=r"^language:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question))
    app.add_error_handler(error_handler)

    logger.info("Bot starting (polling)...")
    app.run_polling()


if __name__ == "__main__":
    main()
