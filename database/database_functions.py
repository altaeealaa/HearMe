from database.database_setup import conn, cursor

# --- User Functions ---

def add_user(user_id, name,username, role, language):
    cursor.execute('''
        INSERT INTO users (user_id, name,username, role, language)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE SET
            name = EXCLUDED.name,
            username = EXCLUDED.username,
            role = EXCLUDED.role,
            language = EXCLUDED.language
    ''', (user_id, name, username, role, language))
    conn.commit()


def update_user_role(user_id, new_role):
    cursor.execute('''
        UPDATE users SET role = %s WHERE user_id = %s
    ''', (new_role, user_id))
    conn.commit()


def get_user_role(user_id):
    cursor.execute('SELECT role FROM users WHERE user_id = %s', (user_id,))
    result = cursor.fetchone()
    return result[0] if result else None


def update_user_language(user_id, new_language):
    cursor.execute('''
        UPDATE users SET language = %s WHERE user_id = %s
    ''', (new_language, user_id))
    conn.commit()


def get_user_language(user_id):
    cursor.execute('SELECT language FROM users WHERE user_id = %s', (user_id,))
    result = cursor.fetchone()
    return result[0] if result else None


# --- Group Functions ---

def save_group(group_id, group_name):
    cursor.execute('''
        INSERT INTO groups (group_id, group_name)
        VALUES (%s, %s)
        ON CONFLICT (group_id) DO UPDATE SET group_name = EXCLUDED.group_name
        RETURNING group_id
    ''', (group_id, group_name))
    result = cursor.fetchone()
    conn.commit()
    return result[0]


def add_user_to_group(user_id, group_id):
    # Check user role
    cursor.execute('SELECT role FROM users WHERE user_id = %s', (user_id,))
    result = cursor.fetchone()
    if not result:
        return  # user not registered
    role = result[0]

    if role == 'blind':
        cursor.execute('''
            INSERT INTO user_groups (user_id, group_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        ''', (user_id, group_id))
        conn.commit()


def get_user_groups(user_id):
    cursor.execute('''
        SELECT g.group_id, g.group_name
        FROM groups g
        JOIN user_groups ug ON g.group_id = ug.group_id
        WHERE ug.user_id = %s
    ''', (user_id,))
    return cursor.fetchall()



# --- Message Functions ---

def save_group_message(group_id, group_name, sender_id, sender_name, message_text):
    # Step 1: Save the message
    cursor.execute('''
        INSERT INTO messages (group_id, group_name, sender_id, sender_name, message_text)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING message_id
    ''', (group_id, group_name, sender_id, sender_name, message_text))
    message_id = cursor.fetchone()[0]

    # Step 2: Get all blind users in the group (except the sender)
    cursor.execute('''
        SELECT u.user_id
        FROM users u
        JOIN user_groups ug ON u.user_id = ug.user_id
        WHERE ug.group_id = %s AND u.role = 'blind' AND u.user_id != %s
    ''', (group_id, sender_id))
    blind_user_ids = cursor.fetchall()

    # Step 3: Insert delivery tracking for each blind user
    for (user_id,) in blind_user_ids:
        cursor.execute('''
            INSERT INTO message_deliveries (message_id, user_id)
            VALUES (%s, %s)
        ''', (message_id, user_id))

    conn.commit()



def get_undelivered_messages(user_id, group_id):
    cursor.execute('''
        SELECT m.sender_name, m.message_text, m.message_id
        FROM messages m
        JOIN message_deliveries d ON m.message_id = d.message_id
        WHERE d.user_id = %s AND d.seen = FALSE AND m.group_id = %s
        ORDER BY m.created_at ASC
    ''', (user_id, group_id))
    return cursor.fetchall()



def mark_messages_as_delivered(user_id, message_ids):
    if not message_ids:
        return  # No messages to mark

    cursor.executemany('''
        UPDATE message_deliveries
        SET delivered = TRUE
        WHERE user_id = %s AND message_id = %s
    ''', [(user_id, message_id) for message_id in message_ids])
    conn.commit()

    # ✅ Trigger cleanup immediately after marking delivered
    delete_fully_delivered_messages()





def delete_fully_delivered_messages():
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



def get_user_id_by_username(username):
    username = username.lstrip('@')  # Remove '@' if it exists
    cursor.execute('''
        SELECT user_id FROM users WHERE username = %s
    ''', (username,))
    result = cursor.fetchone()
    return result[0] if result else None



def is_user_in_group(user_id: int, group_id: int) -> bool:
    cursor.execute('''
            SELECT 1 FROM user_groups
            WHERE user_id = %s AND group_id = %s
            LIMIT 1
        ''', (user_id, group_id))
    result = cursor.fetchone()
    return result is not None