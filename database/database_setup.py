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
               role TEXT,
               language TEXT DEFAULT 'arabic'
               )
               ''')

conn.commit()