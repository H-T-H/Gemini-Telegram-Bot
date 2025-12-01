import sqlite3
import threading
import json
from datetime import datetime

class Database:
    def __init__(self, db_file="bot_database.db"):
        self.db_file = db_file
        self.lock = threading.Lock()
        self.init_db()

    def init_db(self):
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            # Create table for chat history
            # content_type: 'text' or 'image' or 'audio' (though currently we mostly store text representation or file IDs?)
            # For Gemini history, we primarily need the text content.
            # If we want to support multimodal history (images/audio sent previously), we need to store them as blobs or paths.
            # For now, let's focus on text history which is the most critical for context.
            # Gemini SDK history expects parts.

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Table for user settings (e.g. selected model)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id TEXT PRIMARY KEY,
                    model_id TEXT,
                    additional_config TEXT
                )
            ''')

            conn.commit()
            conn.close()

    def add_message(self, user_id, role, content):
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('INSERT INTO messages (user_id, role, content) VALUES (?, ?, ?)', (str(user_id), role, content))
            conn.commit()
            conn.close()

    def get_history(self, user_id, limit=50):
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('SELECT role, content FROM messages WHERE user_id = ? ORDER BY id ASC', (str(user_id),))
            rows = cursor.fetchall()
            conn.close()
            # If we want to limit context window, we can slice here, but taking the LAST 'limit' messages is better.
            # However, `chats.create` expects history in chronological order.
            # So if we limit, we should take the last N rows.

            if len(rows) > limit:
                return rows[-limit:]
            return rows

    def clear_history(self, user_id):
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM messages WHERE user_id = ?', (str(user_id),))
            conn.commit()
            conn.close()

    def set_user_model(self, user_id, model_id):
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_settings (user_id, model_id) VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET model_id=excluded.model_id
            ''', (str(user_id), model_id))
            conn.commit()
            conn.close()

    def get_user_model(self, user_id):
        with self.lock:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('SELECT model_id FROM user_settings WHERE user_id = ?', (str(user_id),))
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else None

# Singleton instance
db = Database()
