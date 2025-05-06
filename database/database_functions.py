from database.database_setup import conn, cursor

def add_user(user_id, name, role, language):
    cursor.execute('''
                   INSERT OR REPLACE INTO users (user_id, name, role, language)
                   VALUES (?, ?, ?, ?)
                   ''', (user_id, name, role, language))
    conn.commit()


def get_user_role(user_id):
    cursor.execute('''
                   SELECT role FROM users WHERE user_id = ?
                   ''', (user_id,))
    result = cursor.fetchone()
    if result:
        return result[0]  # Return the role if found
    return None  # Return None if no role is found

def get_preffered_language(user_id):
    cursor.execute('''
                   SELECT language FROM users WHERE user_id = ?
                   ''', (user_id,))
    result = cursor.fetchone()
    if result:
        return result[0]
    return None

def save_group_message(group_name, sender_id, sender_name, message_text):
    cursor.execute('''
                   INSERT INTO messages (group_name, sender_id, sender_name, message_text)
                   VALUES (?, ?, ?, ?)
                   ''', (group_name, sender_id, sender_name, message_text))
    conn.commit()


def save_group(group_id, group_name):
    cursor.execute('''
                   INSERT OR IGNORE INTO groups (group_id, group_name)
                   VALUES (?, ?)
                   ''', (group_id, group_name))
    conn.commit()
