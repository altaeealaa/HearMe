from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.database import add_user, get_user_role
from database.database import conn, cursor
from database.database import save_group_message, save_group
from services.tts_service import text_to_speech, handle_after_ask
import sqlite3
#import pyttsx3

# Handle /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_role = get_user_role(user_id)  # Check if the user already has a role in the database
    if user_role:
        # If user already has a role, show them their role
        await update.message.reply_text(f"Your role is already set to {user_role.capitalize()}. Use /check to continue.")
        return  # Exit the function, no need to show the role selection

    # If no role is set, allow the user to choose their role
    keyboard = [
        [InlineKeyboardButton("🔵 I am blind", callback_data='role_blind')],
        [InlineKeyboardButton("🟢 I am sighted", callback_data='role_sighted')]
        ]
    markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Welcome! Are you a blind user or a sighted user?",
        reply_markup=markup
        )



# --- Handle Role Selection ---
async def set_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    name = query.from_user.full_name
    role = 'blind' if query.data == 'role_blind' else 'sighted'
    
    add_user(user_id,name,role)
    await query.edit_message_text(f"✅ Your role is set to {role.capitalize()}. Use /check to continue.")


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



