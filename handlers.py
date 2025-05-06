from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.database_functions import add_user, get_user_role, get_preffered_language
from database.database_setup import conn, cursor
from database.database_functions import save_group_message, save_group
from services.tts_service import text_to_speech, handle_after_ask
from services.stt_service import speech_to_text
import sqlite3
import string

def normalize_text(text):
    # Convert to lowercase and strip trailing punctuation
    return text.lower().strip(string.punctuation)

# Handle /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_role = get_user_role(user_id)  # Check if the user already has a role in the database
    if user_role:
        # If user already has a role, show them their role
        replied_voice = await text_to_speech(f"Your role is already set to {user_role.capitalize()}. Use /check to continue.")
        await update.message.reply_voice(replied_voice)
        return  # Exit the function, no need to show the role selection

    # If no role is set, allow the user to choose their role
    ask_role = "Welcome to HearMe! I'm a voice-based assistant designed to help you navigate and interact with content using speech. To get started, could you please let me know if you are blind or sighted? Reply by a voice"
    ask_rule_voice = await text_to_speech(ask_role)
    await update.message.reply_voice(ask_rule_voice)


async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    preffered_language = get_preffered_language(user_id)
    if preffered_language:
        language_in_voice = await text_to_speech(f"The language is already set to {preffered_language}")
        await update.message.reply_voice(language_in_voice)
        return 

    ask_language = "Please specify the language you prefer me to communicate with, Arabic or English. الرجاء اختيار اللغة التي تفضّلون التواصل معي بها، العربية أو الانجليزية."
    ask_language_voice = await text_to_speech(ask_language)
    await update.message.reply_voice(ask_language_voice)

async def reply_after_langauge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice
    user_input_text = normalize_text( await speech_to_text(voice))
    print(user_input_text)
    # Check if the langiage is Arabic ro English
    if user_input_text == "arabic":
        language = "arabic"
    elif user_input_text == "sighted":
        language = "english"
    else:
        # If the bot didn't understand, ask the user again
        await update.message.reply_voice(voice= await text_to_speech("I didn't understand. Please say Arabic or English"))
        return  # Exit the function to wait for the user to say again

    # After determining the language, store it in the database
    user_id = update.message.from_user.id
    name = update.message.from_user.full_name
    role = get_user_role(user_id)
    add_user(user_id, name, role, language)

    # Send a confirmation voice message
    confirmation_text = f"The language is set to {language.capitalize()}. Use the check command to continue."
    await update.message.reply_voice(voice=await text_to_speech(confirmation_text))

# --- Handle Role Selection ---
async def set_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice
    user_input_text = normalize_text( await speech_to_text(voice))
    print(user_input_text)
    # Check if the transcribed text is 'blind' or 'sighted' and set the role
    if user_input_text == "blind":
        role = "blind"
    elif user_input_text == "sighted":
        role = "sighted"
    else:
        # If the bot didn't understand, ask the user again
        await update.message.reply_voice(voice= await text_to_speech("I didn't understand. Please say 'blind' or 'sighted'."))
        return  # Exit the function to wait for the user to say again

    # After determining the role, store it in the database
    user_id = update.message.from_user.id
    name = update.message.from_user.full_name
    add_user(user_id, name, role)

    # Send a confirmation voice message
    confirmation_text = f"Your role is set to {role.capitalize()}. Use the check command to continue."
    await update.message.reply_voice(voice=await text_to_speech(confirmation_text))


async def handle_group_message(update: Update, context):
    message = update.effective_message
    group_name = update.effective_chat.title
    group_id = update.effective_chat.id
    sender = message.from_user
    sender_name = sender.full_name
    text = message.text
    
    save_group_message(group_name, sender.id, sender_name, text)
    save_group(group_id, group_name)
    
    if "group_map" not in context.bot_data:
        context.bot_data["group_map"] = {}
        context.bot_data["group_map"][group_name] = group_id
       
    print(f"[SAVED] From {sender_name} in Group {group_name}: {text}")



# --- /check Command ---
async def check_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    cursor.execute("SELECT role FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()

    if not result or result[0] != 'blind':
        await update.message.reply_text("This command is only for blind users.")
        return
    
    cursor.execute("""
        SELECT DISTINCT group_name 
        FROM messages 
        WHERE group_name IS NOT NULL 
          AND TRIM(group_name) != '' 
          AND group_name != 'None'
    """)
    group_names = cursor.fetchall()

    if group_names:
        response = "You have new messages from these groups:\n"
        for group in group_names:
            response += f"- {group[0]}\n"
        response += "\nReply with the group name you want to listen to, or a group name that's not listed here and you want to talk with."
    else:
        response = "You have no new messages.\nIs there any group you want to send a message to? Just reply with the group name."

    context.user_data["awaiting_group_choice"] = True

    response_voice = await text_to_speech(response)
    await update.message.reply_voice(response_voice)




# --- Handle Group Choice ---
async def handle_group_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    group_choice = update.message.text.strip()

    # Check if group exists
    cursor.execute('''
        SELECT 1 FROM groups 
        WHERE group_name = ?
    ''', (group_choice,))
    group_exists = cursor.fetchone()

    if not group_exists:
        msg = "This group is not found. Try again."
        await update.message.reply_text(msg)
        await text_to_speech(msg)
        context.user_data["awaiting_group_choice"] = False
        return

    # Get messages
    cursor.execute('''
        SELECT sender_name, message_text FROM messages
        WHERE group_name = ?
        ORDER BY rowid ASC
    ''', (group_choice,))
    messages = cursor.fetchall()

    if messages:
        voice_output = ""
        for sender_name, message_text in messages:
            voice_output += f"{sender_name} said, {message_text}. "

        full_voice = voice_output + "Do you want to reply? (Say 'yes' or 'no')"

        output_voice = await text_to_speech(full_voice)
        await update.message.reply_voice(output_voice)
        await handle_after_ask(update, context)

        # Delete messages
        cursor.execute('''
            DELETE FROM messages
            WHERE group_name = ?
        ''', (group_choice,))
        conn.commit()

        print(f"[DELETED] All messages from Group {group_choice}")
    else:
        msg = text_to_speech("Okay. Record your voice and I’ll send it to the group.")
        await update.message.reply_voice(msg)
        #await send_voice_message(update, msg)

    context.user_data["selected_group"] = group_choice
    context.user_data["awaiting_group_choice"] = False




# --- Handle Text ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_group_choice"):
        await handle_group_choice(update, context)



