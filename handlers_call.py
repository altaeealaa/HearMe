from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import BOT_TOKEN
from handlers import start, set_role, handle_group_message, set_language
from handlers import check_messages, handle_text
from services.image import handle_photo

def create_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    # Add command and callback handlers
     
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("language", set_language))
    app.add_handler(MessageHandler(filters.VOICE, set_role))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, handle_group_message))
    app.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.GROUPS, handle_photo))
    app.add_handler(CommandHandler("check", check_messages))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return app

