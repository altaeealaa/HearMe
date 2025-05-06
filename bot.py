
from telegram import Update
from telegram.ext import ContextTypes
from services.stt_service import speech_to_text, speech_to_text_when_update
from telegram.ext import ApplicationBuilder
from config import BOT_TOKEN, WHISPER_MODEL
from telegram.ext import MessageHandler, filters, CommandHandler
from services.tts_service import text_to_speech, text_to_speech_when_update, ask_to_reply, handle_after_ask
'''
# Load the Whisper model once globally
#model_for_sst = whisper.load_model(WHISPER_MODEL)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = await speech_to_text_when_update(update, context)
    if text:
        await update.message.reply_text(f"{text}")
    else:
        await update.message.reply_text("⚠️ Couldn't understand the voice message.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await text_to_speech_when_update(update, context)

async def handle_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ask_to_reply(update, context)

async def handle_reply_after_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    handle_after_ask(update, context)


# Async main
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.VOICE, handle_after_ask))
#app.add_handler(MessageHandler(filters.TEXT, handle_text))
app.add_handler(CommandHandler("ask", ask_to_reply))  # Trigger with /ask
#app.add_handler(MessageHandler(filters.VOICE, handle_voice_reply))
app.run_polling()'''
