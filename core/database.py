import aiosqlite
import asyncio # May be needed for async lock if multiple writes are expected

DB_SETTINGS_PATH = "settings.db"
DB_MEMORY_PATH = "memory.db" # New constant
MAX_CHAT_HISTORY_MESSAGES = 10 # New constant: Store last 10 messages (user + model)
DEFAULT_QUOTA = 100
DEFAULT_MODEL_KIND = "flash" # 'flash' or 'pro'

# Lock for database operations if needed, though aiosqlite handles some concurrency.
# For simplicity, we'll start without an explicit asyncio.Lock here,
# assuming operations are not highly concurrent or are managed by the caller.
# db_lock = asyncio.Lock() 

async def initialize_settings_db():
    """Initializes the settings.db and creates the user_settings table if it doesn't exist."""
    async with aiosqlite.connect(DB_SETTINGS_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                default_model_kind TEXT NOT NULL DEFAULT ?,
                quota INTEGER NOT NULL DEFAULT ?
            )
        """, (DEFAULT_MODEL_KIND, DEFAULT_QUOTA))
        await db.commit()

async def get_user_settings(user_id: int) -> tuple | None:
    """
    Retrieves a user's settings (default_model_kind, quota).
    Returns a tuple (default_model_kind, quota) or None if not found.
    """
    async with aiosqlite.connect(DB_SETTINGS_PATH) as db:
        async with db.execute("SELECT default_model_kind, quota FROM user_settings WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()

async def add_or_update_user_settings(user_id: int, model_kind: str | None = None, quota: int | None = None):
    """
    Adds a new user or updates existing user's settings.
    If model_kind or quota is None, it keeps the existing or default value.
    """
    async with aiosqlite.connect(DB_SETTINGS_PATH) as db:
        # Try to fetch existing settings
        # For robustness in this specific function, we'll re-fetch inside the same connection
        # to avoid issues with the nested call to get_user_settings which opens its own connection.
        async with db.execute("SELECT default_model_kind, quota FROM user_settings WHERE user_id = ?", (user_id,)) as cursor:
            existing = await cursor.fetchone()
        
        current_model_kind = DEFAULT_MODEL_KIND
        current_quota = DEFAULT_QUOTA

        if existing:
            current_model_kind = existing[0]
            current_quota = existing[1]
        
        new_model_kind = model_kind if model_kind is not None else current_model_kind
        new_quota = quota if quota is not None else current_quota
            
        await db.execute("""
            INSERT INTO user_settings (user_id, default_model_kind, quota)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                default_model_kind = excluded.default_model_kind,
                quota = excluded.quota
        """, (user_id, new_model_kind, new_quota))
        await db.commit()

async def get_default_model(user_id: int) -> str:
    """Gets the user's default model. Creates settings with defaults if user doesn't exist."""
    settings = await get_user_settings(user_id)
    if settings:
        return settings[0]
    else:
        # User not found, create with defaults and return default model
        await add_or_update_user_settings(user_id, DEFAULT_MODEL_KIND, DEFAULT_QUOTA)
        return DEFAULT_MODEL_KIND

async def set_default_model(user_id: int, model_kind: str):
    """Sets the user's default model."""
    # This will create user with default quota if not exists, or update existing.
    await add_or_update_user_settings(user_id, model_kind=model_kind)

async def get_quota(user_id: int) -> int:
    """Gets the user's current quota. Creates settings with defaults if user doesn't exist."""
    settings = await get_user_settings(user_id)
    if settings:
        return settings[1]
    else:
        # User not found, create with defaults and return default quota
        await add_or_update_user_settings(user_id, DEFAULT_MODEL_KIND, DEFAULT_QUOTA)
        return DEFAULT_QUOTA

async def decrement_quota(user_id: int, amount: int = 1) -> bool:
    """
    Decrements the user's quota. Returns True if successful (quota > 0 after decrement),
    False otherwise (quota was already 0 or less).
    Creates settings with defaults if user doesn't exist, but new quota will be default - amount.
    """
    current_quota = await get_quota(user_id) # Ensures user exists, gets current quota
    
    if current_quota <= 0:
        return False # Already out of quota

    new_quota = max(0, current_quota - amount)
    await add_or_update_user_settings(user_id, quota=new_quota)
    return new_quota >= 0 # Changed to allow quota to be 0 after decrement and still be True

# It might be good to have a main function here to run initialize_settings_db once.
async def ensure_db_initialized():
    # This can be called at bot startup.
    await initialize_settings_db()
    await initialize_memory_db() # Add this line

# New functions for chat history management:
async def initialize_memory_db():
    """Initializes memory.db and creates the chat_history table if it doesn't exist."""
    async with aiosqlite.connect(DB_MEMORY_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL, 
                role TEXT NOT NULL, CHECK(role IN ('user', 'model')),
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_session_timestamp ON chat_history (session_id, timestamp DESC)")
        await db.commit()

async def add_chat_message(session_id: str, role: str, content: str):
    """Adds a message to the chat history for the given session_id."""
    async with aiosqlite.connect(DB_MEMORY_PATH) as db:
        await db.execute(
            "INSERT INTO chat_history (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content)
        )
        # Prune old messages to keep only the last MAX_CHAT_HISTORY_MESSAGES
        await db.execute("""
            DELETE FROM chat_history
            WHERE entry_id NOT IN (
                SELECT entry_id
                FROM chat_history
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            ) AND session_id = ? 
        """, (session_id, MAX_CHAT_HISTORY_MESSAGES, session_id)) # Pass session_id three times
        await db.commit()

async def get_chat_history(session_id: str) -> list[dict[str, any]]:
    """
    Retrieves the last MAX_CHAT_HISTORY_MESSAGES for the session_id,
    formatted for the Gemini API.
    Returns a list of {'role': role, 'parts': [{'text': content}]}.
    """
    history_for_api = []
    async with aiosqlite.connect(DB_MEMORY_PATH) as db:
        # Fetch in ascending order of timestamp to maintain conversation flow
        query = """
            SELECT role, content FROM (
                SELECT role, content, timestamp FROM chat_history
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            ) ORDER BY timestamp ASC
        """
        async with db.execute(query, (session_id, MAX_CHAT_HISTORY_MESSAGES)) as cursor:
            async for row in cursor:
                role, content = row
                history_for_api.append({'role': role, 'parts': [{'text': content}]})
    return history_for_api

async def clear_chat_history(session_id: str):
    """Clears all chat history for the given session_id."""
    async with aiosqlite.connect(DB_MEMORY_PATH) as db:
        await db.execute("DELETE FROM chat_history WHERE session_id = ?", (session_id,))
        await db.commit()
