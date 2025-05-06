import sqlite3

# --- Database Setup ---

conn = sqlite3.connect('users.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
               CREATE TABLE IF NOT EXISTS messages (
               group_name TEXT,
               sender_id INTEGER,
               sender_name TEXT,
               message_text TEXT
               )
               ''')

cursor.execute('''
               CREATE TABLE IF NOT EXISTS groups (
               group_id INTEGER,
               group_name TEXT
               )
               ''')

cursor.execute('''
               CREATE TABLE IF NOT EXISTS users (
               user_id INTEGER PRIMARY KEY,
               name TEXT,
               role TEXT
               )
               ''')

conn.commit()

def add_user(user_id, name, role):
    cursor.execute('''
                   INSERT OR REPLACE INTO users (user_id, name, role)
                   VALUES (?, ?, ?)
                   ''', (user_id, name, role))
    conn.commit()


def get_user_role(user_id):
    cursor.execute('''
                   SELECT role FROM users WHERE user_id = ?
                   ''', (user_id,))
    result = cursor.fetchone()
    if result:
        return result[0]  # Return the role if found
    return None  # Return None if no role is found


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
