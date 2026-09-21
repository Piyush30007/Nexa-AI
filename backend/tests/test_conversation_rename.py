"""
Unit and Integration Tests for Authenticated Conversation Renaming & Deterministic Title Generation (Phase 8.3)
==============================================================================================================
Verifies:
- Authenticated owner can rename their conversation (HTTP 200)
- Renaming updates only the conversation title in the database
- Another authenticated user cannot rename the conversation (HTTP 403 Forbidden)
- Unauthenticated request is rejected (HTTP 401 Unauthorized)
- Empty or whitespace-only title is rejected (HTTP 400 Bad Request)
- Title exceeding 100 characters is rejected (HTTP 400 Bad Request)
- Nonexistent conversation returns HTTP 404 Not Found
- Guest/unassigned conversation (user_id IS NULL) cannot be renamed (HTTP 403 Forbidden)
- Deterministic title generation on first user message persistence
- Existing/custom titles are not overwritten by subsequent user messages
"""

import unittest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, Conversation, Message, get_db
from app.auth.clerk_auth import get_current_user
from app.main import app
from app.services.conversation_service import (
    generate_conversation_title,
    save_user_message,
)


class TestConversationRename(unittest.TestCase):

    def setUp(self):
        # Isolated in-memory SQLite database using StaticPool
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()

    def test_authenticated_owner_can_rename_conversation(self):
        """Authenticated owner can rename their conversation; title updates in DB."""
        db = self.Session()
        now = datetime.now(timezone.utc)
        conv = Conversation(
            id="conv_rename_1",
            user_id="user_alice",
            title="Old Title",
            created_at=now,
        )
        db.add(conv)
        db.commit()
        db.close()

        app.dependency_overrides[get_current_user] = lambda: {
            "id": "user_alice",
            "email": "alice@example.com",
        }

        response = self.client.patch(
            "/api/conversations/conv_rename_1",
            json={"title": "Updated Project Architecture"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], "conv_rename_1")
        self.assertEqual(data["title"], "Updated Project Architecture")

        # Verify DB state
        db = self.Session()
        conv_in_db = db.query(Conversation).filter_by(id="conv_rename_1").first()
        self.assertIsNotNone(conv_in_db)
        self.assertEqual(conv_in_db.title, "Updated Project Architecture")
        db.close()

    def test_wrong_owner_cannot_rename_conversation(self):
        """Another authenticated user cannot rename a conversation they do not own (403 Forbidden)."""
        db = self.Session()
        now = datetime.now(timezone.utc)
        conv = Conversation(
            id="conv_alice_secret",
            user_id="user_alice",
            title="Alice's Private Thoughts",
            created_at=now,
        )
        db.add(conv)
        db.commit()
        db.close()

        # Bob attempts to rename Alice's conversation
        app.dependency_overrides[get_current_user] = lambda: {
            "id": "user_bob",
            "email": "bob@example.com",
        }

        response = self.client.patch(
            "/api/conversations/conv_alice_secret",
            json={"title": "Hacked by Bob"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("forbidden", response.json()["detail"].lower())

        # Verify DB state: title remains unchanged
        db = self.Session()
        conv_in_db = db.query(Conversation).filter_by(id="conv_alice_secret").first()
        self.assertEqual(conv_in_db.title, "Alice's Private Thoughts")
        db.close()

    def test_unauthenticated_rename_is_rejected(self):
        """Unauthenticated request without Clerk token returns 401 Unauthorized."""
        response = self.client.patch(
            "/api/conversations/conv_any",
            json={"title": "New Title"},
        )
        self.assertEqual(response.status_code, 401)

    def test_empty_or_whitespace_title_rejected(self):
        """Empty or whitespace-only title returns 400 Bad Request."""
        db = self.Session()
        now = datetime.now(timezone.utc)
        conv = Conversation(
            id="conv_val_1",
            user_id="user_alice",
            title="Original",
            created_at=now,
        )
        db.add(conv)
        db.commit()
        db.close()

        app.dependency_overrides[get_current_user] = lambda: {
            "id": "user_alice",
            "email": "alice@example.com",
        }

        # Empty string
        res_empty = self.client.patch(
            "/api/conversations/conv_val_1",
            json={"title": ""},
        )
        self.assertEqual(res_empty.status_code, 400)
        self.assertIn("empty", res_empty.json()["detail"].lower())

        # Whitespace-only string
        res_ws = self.client.patch(
            "/api/conversations/conv_val_1",
            json={"title": "    \t   \n  "},
        )
        self.assertEqual(res_ws.status_code, 400)
        self.assertIn("empty", res_ws.json()["detail"].lower())

    def test_excessively_long_title_rejected(self):
        """Title exceeding 100 characters returns 400 Bad Request."""
        db = self.Session()
        now = datetime.now(timezone.utc)
        conv = Conversation(
            id="conv_val_2",
            user_id="user_alice",
            title="Original",
            created_at=now,
        )
        db.add(conv)
        db.commit()
        db.close()

        app.dependency_overrides[get_current_user] = lambda: {
            "id": "user_alice",
            "email": "alice@example.com",
        }

        long_title = "A" * 101
        res = self.client.patch(
            "/api/conversations/conv_val_2",
            json={"title": long_title},
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("exceed", res.json()["detail"].lower())

    def test_nonexistent_conversation_returns_404(self):
        """Renaming a nonexistent conversation returns 404 Not Found."""
        app.dependency_overrides[get_current_user] = lambda: {
            "id": "user_alice",
            "email": "alice@example.com",
        }

        response = self.client.patch(
            "/api/conversations/nonexistent_uuid_999",
            json={"title": "Some Title"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"].lower())

    def test_guest_unowned_conversation_cannot_be_renamed(self):
        """Guest/unowned conversation (user_id IS NULL) cannot be renamed (403 Forbidden)."""
        db = self.Session()
        now = datetime.now(timezone.utc)
        conv = Conversation(
            id="conv_guest_unassigned",
            user_id=None,
            title="Guest Chat",
            created_at=now,
        )
        db.add(conv)
        db.commit()
        db.close()

        app.dependency_overrides[get_current_user] = lambda: {
            "id": "user_alice",
            "email": "alice@example.com",
        }

        response = self.client.patch(
            "/api/conversations/conv_guest_unassigned",
            json={"title": "Alice Claims It"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("forbidden", response.json()["detail"].lower())

    def test_deterministic_title_generation(self):
        """Unit test for generate_conversation_title cleaning and truncation rules."""
        # Strips question prefixes
        self.assertEqual(
            generate_conversation_title("What is the company leave policy?"),
            "Company leave policy",
        )
        self.assertEqual(
            generate_conversation_title("Tell me about health insurance benefits"),
            "Health insurance benefits",
        )
        self.assertEqual(
            generate_conversation_title("How do I request remote work?"),
            "Request remote work",
        )
        self.assertEqual(
            generate_conversation_title("Can you explain the promotion criteria:"),
            "Explain the promotion criteria",
        )
        # Keeps non-prefixed questions clean
        self.assertEqual(
            generate_conversation_title("Remote work policy"),
            "Remote work policy",
        )
        # Fallback for empty
        self.assertEqual(
            generate_conversation_title(""),
            "New conversation",
        )

    def test_save_user_message_sets_generated_title_on_placeholder_conversation(self):
        """First user message automatically updates placeholder title in DB."""
        db = self.Session()
        now = datetime.now(timezone.utc)
        conv = Conversation(
            id="conv_auto_title_1",
            user_id="user_alice",
            title="New conversation",
            created_at=now,
        )
        db.add(conv)
        db.commit()
        db.close()

        db = self.Session()
        save_user_message(
            db=db,
            conversation_id="conv_auto_title_1",
            content="What is the company's remote work policy?",
        )
        db.close()

        db = self.Session()
        updated_conv = db.query(Conversation).filter_by(id="conv_auto_title_1").first()
        self.assertEqual(updated_conv.title, "Company's remote work policy")
        db.close()

    def test_subsequent_user_messages_preserve_custom_title(self):
        """Subsequent user messages do not overwrite an existing or customized title."""
        db = self.Session()
        now = datetime.now(timezone.utc)
        conv = Conversation(
            id="conv_custom_title_1",
            user_id="user_alice",
            title="Custom Project Discussion",
            created_at=now,
        )
        db.add(conv)
        db.commit()
        db.close()

        db = self.Session()
        save_user_message(
            db=db,
            conversation_id="conv_custom_title_1",
            content="What is another question?",
        )
        db.close()

        db = self.Session()
        updated_conv = db.query(Conversation).filter_by(id="conv_custom_title_1").first()
        self.assertEqual(updated_conv.title, "Custom Project Discussion")
        db.close()


if __name__ == "__main__":
    unittest.main()
