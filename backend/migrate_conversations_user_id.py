"""
Explicit Migration Script: Add user_id column to conversations table.
====================================================================
Non-destructive:
- Preserves all existing conversations, messages, documents, chunks, and logs.
- Uses IF NOT EXISTS to ensure idempotency.
- Sets user_id to NULL on existing records (representing guest / unassigned conversations).
"""

import sys
from pathlib import Path

# Ensure backend path is on sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import inspect, text
from database import engine


def migrate():
    print(f"Connecting to database engine: {engine.dialect.name}...")
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        if "conversations" not in tables:
            print("Table 'conversations' does not exist yet. Running create_all...")
            from database import Base
            Base.metadata.create_all(bind=engine)
            print("Created all tables.")
            return

        columns = [c["name"] for c in inspector.get_columns("conversations")]
        print(f"Existing columns in 'conversations': {columns}")

        if "user_id" in columns:
            print("Column 'user_id' already exists in 'conversations'. Migration not required.")
            return

        print("Applying migration: Adding 'user_id' column to 'conversations'...")
        with engine.begin() as conn:
            if engine.dialect.name == "postgresql":
                conn.execute(text("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS user_id VARCHAR;"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_conversations_user_id ON conversations (user_id);"))
            else:
                conn.execute(text("ALTER TABLE conversations ADD COLUMN user_id VARCHAR;"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_conversations_user_id ON conversations (user_id);"))

        # Verify
        inspector = inspect(engine)
        updated_columns = [c["name"] for c in inspector.get_columns("conversations")]
        print(f"Migration completed successfully! Columns now: {updated_columns}")

    except Exception as e:
        print(f"Migration could not complete directly against database connection: {e}")
        print("\nIf applying manually in the Supabase SQL Editor, run:")
        print("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS user_id VARCHAR;")
        print("CREATE INDEX IF NOT EXISTS ix_conversations_user_id ON conversations (user_id);")


if __name__ == "__main__":
    migrate()
