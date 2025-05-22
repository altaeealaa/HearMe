from telegram import Update
from telegram.ext import ContextTypes
from database.database_functions import save_group, save_group_message, get_all_group_names 
from database.database_setup import conn, cursor
from services.tts_service import text_to_speech
from services.stt_service import speech_to_text
from handlers.helper_functions import normalize_text, fuzzy_language_match
from database.database_functions import get_preffered_language 



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

    if message.text:
        # if the meesage is text, save it directly to the database    
        save_group_message(group_name, sender_id, sender_name, normalized_text)
        print(f"[SAVED] From {sender_name} in Group {group_name}: {normalized_text}")
    elif message.voice:
        # if the message is a voice, transcribe it and save the transcribed text
        voice = message.voice
        transcribed = await speech_to_text(voice)
        print(f"[DEBUG] Voice transcribed: {transcribed}")
        normalized = normalize_text(transcribed)
        save_group_message(group_name, sender_id, sender_name, normalized)
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
    language = get_preffered_language(user_id) or "english"

    voice = update.message.voice
    print(f"[DEBUG] Voice content: {voice}")

    if not voice:
        msg = "لم أستلم أي رسالة صوتية. حاول مرة أخرى." if language == "arabic" else "I didn't receive any voice. Please try again."
        await update.message.reply_voice(await text_to_speech(msg))
        return

    try:
        transcribed = await speech_to_text(voice)
        print(f"[DEBUG] Transcribed voice: {transcribed}")
    except Exception as e:
        print(f"[ERROR] Failed to transcribe voice: {e}")
        msg = "حدث خطأ أثناء معالجة صوتك. حاول مرة أخرى." if language == "arabic" else "There was an error processing your voice. Please try again."
        await update.message.reply_voice(await text_to_speech(msg))
        return

    if not transcribed:
        msg = "عذرًا، لم أتمكن من فهم صوتك. حاول مرة أخرى." if language == "arabic" else "Sorry, I couldn't understand your voice. Try again."
        await update.message.reply_voice(await text_to_speech(msg))
        return
    

     # 💡 Handle switch to {group} command
    if await handle_switch_to_command(update, context, transcribed):
        context.user_data["awaiting_group_choice"] = False
        return

    group_choice = normalize_text(transcribed)
    print(f"[DEBUG] Normalized group choice: {group_choice}")

    all_groups = get_all_group_names()
    matched_group = fuzzy_language_match(group_choice, all_groups)

    if not matched_group:
        msg = "لم أجد هذه المجموعة. حاول مرة أخرى." if language == "arabic" else "This group is not found. Try again."
        print(f"[DEBUG] Group not found: {group_choice}")
        await update.message.reply_voice(await text_to_speech(msg))
        return

    group_choice_db = matched_group  # Use the matched group name

    # Get messages
    cursor.execute('''
        SELECT sender_name, message_text FROM messages
        WHERE group_name = ?
        ORDER BY rowid ASC
    ''', (group_choice_db,))
    messages = cursor.fetchall()

    if messages:
        # to group the messages by the same sender
        voice_output = ""
        grouped = []
        prev_sender = None
        current_texts = []

        for sender_name, message_text in messages:
            if sender_name == prev_sender:
                # If the sender is the same as the previous one, append the message
                current_texts.append(message_text)
            else:
                if prev_sender is not None:
                    # If the sender has changed, say sender's name before the new message
                    grouped.append((prev_sender, current_texts))
                prev_sender = sender_name
                current_texts = [message_text]
        # Add the last group
        if prev_sender is not None:
            grouped.append((prev_sender, current_texts))

        # Create the voice output
        for sender, texts in grouped:
            merged_text = ", ".join(texts)
            if language == "arabic":
                voice_output += f"{sender} قال {merged_text}. "
            else:
                voice_output += f"{sender} said {merged_text}. "

        if language == "arabic":
            full_voice = voice_output.strip() + " هل تريد الرد؟ (قل نعم أو لا)"
        else:
            full_voice = voice_output.strip() + " Do you want to reply? (Say 'yes' or 'no')"

        output_voice = await text_to_speech(full_voice)
        await update.message.reply_voice(output_voice)

        context.user_data["awaiting_yes_no_reply"] = True

        # Delete messages
        cursor.execute('''
            DELETE FROM messages
            WHERE group_name = ?
        ''', (group_choice_db,))
        conn.commit()
        print(f"[DELETED] All messages from Group {group_choice_db}")
    else:
        msg = "حسنًا. سجل رسالتك الصوتية وسأرسلها إلى المجموعة." if language == "arabic" else "Okay. Record your voice and I’ll send it to the group."
        await update.message.reply_voice(await text_to_speech(msg))
        context.user_data["awaiting_group_reply"] = True

    context.user_data["selected_group"] = group_choice_db
    context.user_data["awaiting_group_choice"] = False









async def handle_switch_to_command(update: Update, context: ContextTypes.DEFAULT_TYPE, transcribed: str):
    if not transcribed.lower().startswith("switch to"):
        return False  # Not a switch command

    user_id = update.effective_user.id
    language = get_preffered_language(user_id) or "english"

    # Extract the group name after "switch to"
    group_choice = normalize_text(transcribed[9:].strip())
    print(f"[DEBUG] Switch command detected. Target group: {group_choice}")

    # Fuzzy match with all group names
    all_groups = get_all_group_names()
    matched_group = fuzzy_language_match(group_choice, all_groups)

    if not matched_group:
        msg = "لم أتمكن من العثور على هذه المجموعة. حاول مرة أخرى." if language == "arabic" else "I couldn’t find that group. Try another one."
        await update.message.reply_voice(await text_to_speech(msg))
        return True  # Handled as a switch command, but group not found

    group_choice_db = matched_group

    # Fetch group messages
    cursor.execute('''
        SELECT sender_name, message_text FROM messages
        WHERE group_name = ?
        ORDER BY rowid ASC
    ''', (group_choice_db,))
    messages = cursor.fetchall()

    if messages:
        # Group messages by sender
        voice_output = ""
        grouped = []
        prev_sender = None
        current_texts = []

        for sender_name, message_text in messages:
            if sender_name == prev_sender:
                current_texts.append(message_text)
            else:
                if prev_sender is not None:
                    grouped.append((prev_sender, current_texts))
                #there is no previous sender, first message in group
                prev_sender = sender_name
                current_texts = [message_text]
        # for the last message
        if prev_sender is not None:
            grouped.append((prev_sender, current_texts))

        for sender, texts in grouped:
            merged_text = ", ".join(texts)
            voice_output += f"{sender} said {merged_text}. "

        if language == "arabic":
            full_voice = f"تم الانتقال إلى {group_choice_db}. " + voice_output.strip() + " هل تريد الرد؟ (قل نعم أو لا)"
        else:
            full_voice = f"Switched to {group_choice_db}. " + voice_output.strip() + " Do you want to reply? (Say 'yes' or 'no')"
        await update.message.reply_voice(await text_to_speech(full_voice))

        context.user_data["awaiting_yes_no_reply"] = True

        # Delete messages after reading
        cursor.execute('''
            DELETE FROM messages
            WHERE group_name = ?
        ''', (group_choice_db,))
        conn.commit()
    else:
        # No messages in the group, prompt to send one
        if language == "arabic":
            msg = f"تم الانتقال إلى {group_choice_db}. لا توجد رسائل جديدة. هل تريد إرسال رسالة؟"
        else:
            msg = f"Switched to {group_choice_db}. No new messages. Do you want to send one say yes or no?"
        await update.message.reply_voice(await text_to_speech(msg))
        context.user_data["awaiting_yes_no_reply"] = True


    context.user_data["selected_group"] = group_choice_db
    return True  # Handled as a switch command




# handle the response after asking the user if they want to reply
async def handle_after_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    language = get_preffered_language(user_id) or "english"
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
    language = get_preffered_language(user_id) 

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
        cursor.execute("SELECT group_id FROM groups WHERE group_name = ?", (group_name,))
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
        await context.bot.send_voice(chat_id=group_chat_id, voice=voice.file_id)
        if language == "english":
            msg = "Your message has been sent." 
        elif language == "arabic":
            msg = "تم إرسال رسالتك."
        voice_reply = await text_to_speech(msg)
        await update.message.reply_voice(voice_reply)
        # Reset state after sending
        context.user_data["awaiting_group_reply"] = False
        context.user_data["selected_group"] = None
    except Exception as e:
        print(f"Error sending voice to group: {e}")
        if language == "english":
            msg = "Something went wrong while sending your message." 
        elif language == "arabic":
            msg = "حدث خطأ أثناء إرسال رسالتك."
        voice_reply = await text_to_speech(msg)
        await update.message.reply_voice(voice_reply)
