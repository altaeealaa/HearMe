from telegram import Update
from telegram.ext import ContextTypes
from database.database_functions import save_group, save_group_message, get_user_groups 
from database.database_setup import conn, cursor
from services.tts_service import text_to_speech
from services.stt_service import speech_to_text
from handlers.helper_functions import normalize_text, fuzzy_language_match, get_normalized_user_groups
from database.database_functions import get_user_language, add_user_to_group
import datetime


# --- Handle Group Message ---
#saves messages incoming from groups to database
async def handle_group_message(update: Update, context):
    message = update.effective_message
    group_name = update.effective_chat.title
    group_id = update.effective_chat.id
    sender = message.from_user
    sender_name = sender.full_name
    sender_id = sender.id
    normalized_text = normalize_text(message.text or "") or ""

    # Save group info first (only once due to INSERT OR IGNORE)
    save_group(group_id, group_name)

    add_user_to_group(sender_id, group_id)

    if message.text:
        # if the meesage is text, save it directly to the database    
        save_group_message(group_id, group_name, sender_id, sender_name, normalized_text)
        print(f"[SAVED] From {sender_name} in Group {group_name}: {normalized_text}")
    elif message.voice:
        # if the message is a voice, transcribe it and save the transcribed text
        voice = message.voice
        transcribed = await speech_to_text(voice)
        print(f"[DEBUG] Voice transcribed: {transcribed}")
        normalized = normalize_text(transcribed)
        save_group_message(group_id, group_name, sender_id, sender_name, normalized)
        print(f"[SAVED] From {sender_name} in Group {group_name}: {normalized}")

    # Track group_map in memory
    # This is a dictionary to map group names to their IDs
    if "group_map" not in context.bot_data:
        context.bot_data["group_map"] = {}
    context.bot_data["group_map"][group_name] = group_id





# --- Handle Group Choice ---
async def handle_group_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_group_choice"):
        return

    user_id = update.effective_user.id
    language = get_user_language(user_id) or "english"

    voice = update.message.voice
    if not voice:
        msg = "لم أستلم أي رسالة صوتية. حاول مرة أخرى." if language == "arabic" else "I didn't receive any voice. Please try again."
        await update.message.reply_voice(await text_to_speech(msg))
        return

    try:
        transcribed = await speech_to_text(voice)
    except Exception as e:
        msg = "حدث خطأ أثناء معالجة صوتك. حاول مرة أخرى." if language == "arabic" else "There was an error processing your voice. Please try again."
        await update.message.reply_voice(await text_to_speech(msg))
        return

    if not transcribed:
        msg = "عذرًا، لم أتمكن من فهم صوتك. حاول مرة أخرى." if language == "arabic" else "Sorry, I couldn't understand your voice. Try again."
        await update.message.reply_voice(await text_to_speech(msg))
        return

    if await handle_switch_to_command(update, context, transcribed):
        context.user_data["awaiting_group_choice"] = False
        return

    group_choice = normalize_text(transcribed)
    user_group = get_user_groups(user_id)
    normalized_dict = get_normalized_user_groups(user_group)
    matched_normalized = fuzzy_language_match(group_choice, list(normalized_dict.keys()))

    if not matched_normalized:
        msg = "لم أجد هذه المجموعة. حاول مرة أخرى." if language == "arabic" else "This group is not found. Try again."
        await update.message.reply_voice(await text_to_speech(msg))
        return

    group_id, original_name = normalized_dict[matched_normalized]


    # Fetch messages not delivered to this blind user
    cursor.execute('''
        SELECT m.message_id, m.sender_name, m.message_text
        FROM messages m
        LEFT JOIN message_deliveries d ON m.message_id = d.message_id AND d.user_id = %s
        WHERE m.group_id = %s AND (d.seen IS NULL OR d.seen = FALSE)
        ORDER BY m.created_at ASC
    ''', (user_id, group_id))
    messages = cursor.fetchall()

    if messages:
        voice_output = ""
        grouped = []
        prev_sender = None
        current_texts = []

        message_ids_to_mark = []

        for message_id, sender_name, message_text in messages:
            message_ids_to_mark.append(message_id)
            if sender_name == prev_sender:
                current_texts.append(message_text)
            else:
                if prev_sender is not None:
                    grouped.append((prev_sender, current_texts))
                prev_sender = sender_name
                current_texts = [message_text]
        if prev_sender is not None:
            grouped.append((prev_sender, current_texts))

        for sender, texts in grouped:
            merged_text = ", ".join(texts)
            voice_output += f"{sender} said {merged_text}. "

        full_voice = voice_output.strip()
        full_voice += " هل تريد الرد؟ (قل نعم أو لا)" if language == "arabic" else " Do you want to reply? (Say 'yes' or 'no')"

        await update.message.reply_voice(await text_to_speech(full_voice))

        context.user_data["awaiting_yes_no_reply"] = True
        context.user_data["selected_group"] = original_name
        context.user_data["awaiting_group_choice"] = False

        # Mark messages as delivered for this blind user
        cursor.executemany('''
            INSERT INTO message_deliveries (message_id, user_id, seen)
            VALUES (%s, %s, TRUE)
            ON CONFLICT (message_id, user_id) DO UPDATE SET seen = TRUE
        ''', [(mid, user_id) for mid in message_ids_to_mark])
        conn.commit()

        # Delete messages that are fully delivered to all blind users in that group
        cursor.execute('''
            DELETE FROM messages
            WHERE message_id IN (
                SELECT m.message_id
                FROM messages m
                JOIN message_deliveries d ON m.message_id = d.message_id
                JOIN users u ON d.user_id = u.user_id
                WHERE u.role = 'blind'
                GROUP BY m.message_id
                HAVING BOOL_AND(d.seen) = TRUE
            )
        ''')
        conn.commit()
    else:
        msg = "لا توجد رسائل جديدة. هل تريد إرسال رسالة قل نعم أو لا ؟" if language == "arabic" else "No new messages. Do you want to send one say yes or no?"
        await update.message.reply_voice(await text_to_speech(msg))
        context.user_data["awaiting_yes_no_reply"] = True

    context.user_data["selected_group"] = original_name
    context.user_data["awaiting_group_choice"] = False

        





async def handle_switch_to_command(update: Update, context: ContextTypes.DEFAULT_TYPE, transcribed: str):
    if not transcribed.lower().startswith("switch to"):
        return False  # Not a switch command

    user_id = update.effective_user.id
    language = get_user_language(user_id) or "english"

    # Extract the group name after "switch to"
    group_choice = normalize_text(transcribed)
    print(f"[DEBUG] Normalized group choice: {group_choice}")

    user_group = get_user_groups(user_id) # List of (group_id, group_name)
    normalized_dict = get_normalized_user_groups(user_group) # dict: normalized_name -> (group_id, original_name)

    matched_normalized = fuzzy_language_match(group_choice, list(normalized_dict.keys()))
    print(f"matched: {matched_normalized}")

    if not matched_normalized:
        msg = "لم أجد هذه المجموعة. حاول مرة أخرى." if language == "arabic" else "This group is not found. Try again."
        print(f"[DEBUG] Group not found: {group_choice}")
        await update.message.reply_voice(await text_to_speech(msg))
        return

    if not matched_normalized:
        msg = "لم أتمكن من العثور على هذه المجموعة. حاول مرة أخرى." if language == "arabic" else "I couldn’t find that group. Try another one."
        await update.message.reply_voice(await text_to_speech(msg))
        return True  # Handled as a switch command, but group not found
    
    group_id, original_name = normalized_dict[matched_normalized]

    #Get group_id for matched group_name
    cursor.execute('SELECT group_id FROM groups WHERE group_name ILIKE %s', (original_name,))
    group_row = cursor.fetchone()
    if not group_row:
        msg = "لم أجد هذه المجموعة في قاعدة البيانات." if language == "arabic" else "Group not found in the database."
        await update.message.reply_voice(await text_to_speech(msg))
        return

    group_id = group_row[0]

    # Fetch messages not delivered to this blind user
    cursor.execute('''
        SELECT m.message_id, m.sender_name, m.message_text
        FROM messages m
        LEFT JOIN message_deliveries d ON m.message_id = d.message_id AND d.user_id = %s
        WHERE m.group_id = %s AND (d.seen IS NULL OR d.seen = FALSE)
        ORDER BY m.created_at ASC
    ''', (user_id, group_id))
    messages = cursor.fetchall()

    if messages:
        voice_output = ""
        grouped = []
        prev_sender = None
        current_texts = []

        message_ids_to_mark = []

        for message_id, sender_name, message_text in messages:
            message_ids_to_mark.append(message_id)
            if sender_name == prev_sender:
                current_texts.append(message_text)
            else:
                if prev_sender is not None:
                    grouped.append((prev_sender, current_texts))
                prev_sender = sender_name
                current_texts = [message_text]
        if prev_sender is not None:
            grouped.append((prev_sender, current_texts))

        for sender, texts in grouped:
            merged_text = ", ".join(texts)
            voice_output += f"{sender} said {merged_text}. "

        if language == "arabic":
            full_voice = f"تم الانتقال إلى {original_name}. " + voice_output.strip() + " هل تريد الرد؟ (قل نعم أو لا)"
        else:
            full_voice = f"Switched to {original_name}. " + voice_output.strip() + " Do you want to reply? (Say 'yes' or 'no')"
        await update.message.reply_voice(await text_to_speech(full_voice))

        context.user_data["awaiting_yes_no_reply"] = True
        context.user_data["selected_group"] = original_name
        context.user_data["awaiting_group_choice"] = False

        # Mark messages as delivered for this blind user
        cursor.executemany('''
            INSERT INTO message_deliveries (message_id, user_id, seen)
            VALUES (%s, %s, TRUE)
            ON CONFLICT (message_id, user_id) DO UPDATE SET seen = TRUE
        ''', [(mid, user_id) for mid in message_ids_to_mark])
        conn.commit()

        # Delete messages that are fully delivered to all blind users in that group
        cursor.execute('''
            DELETE FROM messages
            WHERE message_id IN (
                SELECT m.message_id
                FROM messages m
                JOIN message_deliveries d ON m.message_id = d.message_id
                JOIN users u ON d.user_id = u.user_id
                WHERE u.role = 'blind'
                GROUP BY m.message_id
                HAVING BOOL_AND(d.seen) = TRUE
            )
        ''')
        conn.commit()
    
    else:
        # No messages in the group, prompt to send one
        if language == "arabic":
            msg = f"تم الانتقال إلى {original_name}. لا توجد رسائل جديدة. هل تريد إرسال رسالة قل نعم أو لا ؟"
        else:
            msg = f"Switched to {original_name}. No new messages. Do you want to send one say yes or no?"
        await update.message.reply_voice(await text_to_speech(msg))
        context.user_data["awaiting_yes_no_reply"] = True


    context.user_data["selected_group"] = original_name
    return True  # Handled as a switch command





# handle the response after asking the user if they want to reply
async def handle_after_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    language = get_user_language(user_id) or "english"
    yes_words = ['yes', 'اجل', 'نعم']
    no_words = ['no', 'لا', 'كلا']

    if update.message.voice:
        try:
            user_response = await speech_to_text(update.message.voice)
            normalized_response = normalize_text(user_response)
            print(f"[DEBUG] User said (normalized): {normalized_response}")

            # Fuzzy match for yes/no
            yes_match = fuzzy_language_match(normalized_response, yes_words)
            no_match = fuzzy_language_match(normalized_response, no_words)

            if yes_match:
                msg = "Please send a voice message." if language == "english" else "يرجى إرسال رسالة صوتية."
                voice_reply = await text_to_speech(msg)
                await update.message.reply_voice(voice_reply)
                context.user_data["awaiting_group_reply"] = True
            elif no_match:
                msg = "Okay, no reply needed." if language == "english" else "حسنًا، لا حاجة للرد."
                voice_reply = await text_to_speech(msg)
                await update.message.reply_voice(voice_reply)
            else:
                msg = "I didn't understand. Please say yes or no." if language == "english" else "لم أفهم. الرجاء قول نعم أو لا."
                context.user_data["awaiting_yes_no_reply"] = True
                voice_reply = await text_to_speech(msg)
                await update.message.reply_voice(voice_reply)

        except Exception as e:
            print(f"[ERROR] Error processing response: {e}")
            msg = "There was an error understanding you. Try again." if language == "english" else "حدث خطأ أثناء الفهم. حاول مرة أخرى."
            voice_reply = await text_to_speech(msg)
            await update.message.reply_voice(voice_reply)





# Handles sending a user's voice reply to the selected group.
async def handle_voice_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    language = get_user_language(user_id) 
    name = update.effective_chat.full_name

    # Check if the bot is expecting a group reply
    if not context.user_data.get("awaiting_group_reply"):
        if language == "english":
            msg = "I wasn’t expecting a voice message now. Please select a group first." 
        elif language == "arabic":
            msg = "لم أكن أتوقع رسالة صوتية الآن. يرجى اختيار مجموعة أولاً."
        voice_reply = await text_to_speech(msg)
        await update.message.reply_voice(voice_reply)
        return

    # Check if a group has been selected
    if "selected_group" not in context.user_data:
        if language == "english":
            msg = "You haven’t selected a group to send your message to." 
        elif language == "arabic":
            msg = "لم تقم باختيار مجموعة لإرسال رسالتك إليها."
        voice_reply = await text_to_speech(msg)
        await update.message.reply_voice(voice_reply)
        return

    group_name = context.user_data["selected_group"]
    # Try to get the group chat ID from the in-memory group_map
    group_chat_id = context.bot_data.get("group_map", {}).get(group_name)

    # If not found in memory, look up the group ID in the database
    if not group_chat_id:
        cursor.execute("SELECT group_id FROM groups WHERE group_name = %s", (group_name,))
        result = cursor.fetchone()
        if result:
            group_chat_id = result[0]
        else:
            if language == "english":
                msg = "I couldn’t find the group to send your message." 
            elif language == "arabic":
                msg = "لم أتمكن من العثور على المجموعة لإرسال رسالتك."
            voice_reply = await text_to_speech(msg)
            await update.message.reply_voice(voice_reply)
            return

    # Check if the user actually sent a voice message
    voice = update.message.voice
    if not voice:
        if language == "english":
            msg = "I didn’t receive a voice message to send." 
        elif language == "arabic":
            msg = "لم أستلم أي رسالة صوتية لإرسالها."
        voice_reply = await text_to_speech(msg)
        await update.message.reply_voice(voice_reply)
        return
    

    # Try to send the voice message to the group
    try:
        #send voice message
        await context.bot.send_voice(chat_id=group_chat_id, voice=voice.file_id)
        # Send text showing who sent the voice
        sender_text = f"This message is from {username}." if language == "english" else f"هذه الرسالة من {username}."
        await context.bot.send_message(chat_id=group_chat_id, text=sender_text)


        # Check if there are other blind users in the group
        cursor.execute('''
            SELECT ug.user_id
            FROM user_groups ug
            JOIN users u ON ug.user_id = u.user_id
            JOIN groups g ON ug.group_id = g.group_id
            WHERE g.group_id = %s AND u.role = 'blind' AND u.user_id != %s
        ''', (group_chat_id, user_id))
        blind_users = cursor.fetchall()

        if blind_users:
            # Transcribe voice
            transcript = await speech_to_text(voice)

            now = datetime.datetime.now()
            # Insert into messages table
            cursor.execute('''
                INSERT INTO messages (group_id, group_name, sender_id, sender_name, message_text, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING message_id
            ''', (group_chat_id, group_name, user_id, name, transcript, now))
            message_id = cursor.fetchone()[0]

            # Insert message deliveries
            for (blind_user_id,) in blind_users:
                cursor.execute('''
                    INSERT INTO message_deliveries (message_id, user_id, seen)
                    VALUES (%s, %s, FALSE)
                ''', (message_id, blind_user_id))

            # Mark sender as delivered = TRUE
            cursor.execute('''
                INSERT INTO message_deliveries (message_id, user_id, seen)
                VALUES (%s, %s, TRUE)
            ''', (message_id, user_id))

            conn.commit()

        # confirmation
        if language == "english":
            msg = "Your message has been sent. You can record another" 
        elif language == "arabic":
            msg = " تم إرسال رسالتك. يمكنك تسجيل أخرى "
        voice_reply = await text_to_speech(msg)
        await update.message.reply_voice(voice_reply)


        # Reset state after sending
        context.user_data["awaiting_group_reply"] = True
        context.user_data["selected_group"] = group_name


    except Exception as e:
        print(f"Error sending voice to group: {e}")
        if language == "english":
            msg = "Something went wrong while sending your message." 
        elif language == "arabic":
            msg = "حدث خطأ أثناء إرسال رسالتك."
        voice_reply = await text_to_speech(msg)
        await update.message.reply_voice(voice_reply)