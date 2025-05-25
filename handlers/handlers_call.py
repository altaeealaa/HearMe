from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from config import BOT_TOKEN
from handlers.onboarding_handlers import start
from handlers.group_handlers import handle_group_message
from handlers.command_handlers import voice_handler,addblind_command
from services.image import handle_photo

def create_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    # Add command and callback handlers
     
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addblind", addblind_command))
    app.add_handler(MessageHandler(filters.VOICE, voice_handler))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, handle_group_message))
    app.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.GROUPS, handle_photo))
    return app
 
