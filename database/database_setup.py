import os
import psycopg2
from dotenv import load_dotenv

# Load .env
load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

# Create connection and cursor
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# Table creation
def setup_database():
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            name TEXT,
            username TEXT,
            role TEXT,  -- e.g., 'blind', 'sighted'
            language TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            group_id BIGINT PRIMARY KEY,
            group_name TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_groups (
            user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
            group_id BIGINT REFERENCES groups(group_id) ON DELETE CASCADE,
            PRIMARY KEY (user_id, group_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            message_id SERIAL PRIMARY KEY,
            group_id BIGINT REFERENCES groups(group_id) ON DELETE CASCADE,
            group_name TEXT,
            sender_id BIGINT,
            sender_name TEXT,
            message_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP   
        )
    ''')

    # 💡 This tracks which users have received each message
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS message_deliveries (
            message_id BIGINT REFERENCES messages(message_id) ON DELETE CASCADE,
            user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
            seen BOOLEAN DEFAULT FALSE,
            PRIMARY KEY (message_id, user_id)
        )
    ''')

    # Optional performance index
    #cursor.execute('''
        #CREATE INDEX IF NOT EXISTS idx_message_deliveries_delivered
            #ON message_deliveries (user_id, delivered)
    #''')

    conn.commit()
    print("✅ Tables created successfully")
