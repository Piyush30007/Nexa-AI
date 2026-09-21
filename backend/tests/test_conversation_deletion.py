"""
Unit and Integration Tests for Authenticated Conversation Deletion (Phase 6.4)
=============================================================================
Verifies:
- Authenticated owner can delete their conversation
- Deleting a conversation also removes its associated messages (cascade deletion)
- Another authenticated user cannot delete the conversation (403 Forbidden)
- Cross-user deletion leaves the conversation and messages untouched
- Missing or invalid authentication returns HTTP 401
- Guest/unassigned conversation (user_id IS NULL) cannot be deleted (403 Forbidden)
- Nonexistent conversation returns HTTP 404 Not Found
- user_id query parameter spoofing has no effect
- Existing conversation listing and message retrieval reflect deletion
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


class TestConversationDeletion(unittest.TestCase):

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

    def test_authenticated_owner_can_delete_conversation_and_cascade_messages(self):
        """Authenticated owner can delete their conversation; all associated messages are cascade-deleted."""
        db = self.Session()
        now = datetime.now(timezone.utc)
        conv = Conversation(id="conv_to_delete", user_id="user_alice", title="Alice Delete Test", created_at=now)
        msg1 = Message(id="msg_del_1", conversation_id="conv_to_delete", role="user", content="Question 1")
        msg2 = Message(id="msg_del_2", conversation_id="conv_to_delete", role="assistant", content="Answer 1")
        db.add_all([conv, msg1, msg2])
        db.commit()
        db.close()

        app.dependency_overrides[get_current_user] = lambda: {"id": "user_alice", "email": "alice@example.com"}

        response = self.client.delete("/api/conversations/conv_to_delete")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "Conversation deleted successfully."})

        # Verify DB state: conversation removed
        db = self.Session()
        conv_in_db = db.query(Conversation).filter_by(id="conv_to_delete").first()
        self.assertIsNone(conv_in_db)

        # Verify cascade: messages belonging to the conversation are completely removed
        messages_in_db = db.query(Message).filter_by(conversation_id="conv_to_delete").all()
        self.assertEqual(len(messages_in_db), 0)
        db.close()

    def test_cross_user_deletion_forbidden_and_records_untouched(self):
        """Another authenticated user cannot delete a conversation they do not own; records stay intact."""
        db = self.Session()
        conv = Conversation(id="conv_alice_victim", user_id="user_alice", title="Alice Private")
        msg = Message(id="msg_victim", conversation_id="conv_alice_victim", role="user", content="Sensitive text")
        db.add_all([conv, msg])
        db.commit()
        db.close()

        # Attacker user_bob
        app.dependency_overrides[get_current_user] = lambda: {"id": "user_bob", "email": "bob@example.com"}

        response = self.client.delete("/api/conversations/conv_alice_victim")
        self.assertEqual(response.status_code, 403)
        self.assertIn("Forbidden", response.json()["detail"])

        # Verify records are completely untouched
        db = self.Session()
        conv_check = db.query(Conversation).filter_by(id="conv_alice_victim").first()
        self.assertIsNotNone(conv_check)
        self.assertEqual(conv_check.user_id, "user_alice")

        msg_check = db.query(Message).filter_by(conversation_id="conv_alice_victim").all()
        self.assertEqual(len(msg_check), 1)
        self.assertEqual(msg_check[0].content, "Sensitive text")
        db.close()

    def test_missing_authentication_returns_401(self):
        """Unauthenticated delete requests return HTTP 401."""
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]

        response = self.client.delete("/api/conversations/conv_any")
        self.assertEqual(response.status_code, 401)

    def test_guest_conversation_cannot_be_deleted(self):
        """Conversations with user_id = NULL cannot be deleted by anyone (returns 403)."""
        db = self.Session()
        conv = Conversation(id="conv_guest_unowned", user_id=None, title="Guest Chat")
        db.add(conv)
        db.commit()
        db.close()

        app.dependency_overrides[get_current_user] = lambda: {"id": "user_alice", "email": "alice@example.com"}

        response = self.client.delete("/api/conversations/conv_guest_unowned")
        self.assertEqual(response.status_code, 403)

        # Verify guest conversation still exists
        db = self.Session()
        self.assertIsNotNone(db.query(Conversation).filter_by(id="conv_guest_unowned").first())
        db.close()

    def test_nonexistent_conversation_returns_404(self):
        """Deleting a nonexistent conversation returns HTTP 404."""
        app.dependency_overrides[get_current_user] = lambda: {"id": "user_alice", "email": "alice@example.com"}

        response = self.client.delete("/api/conversations/does_not_exist_xyz")
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"].lower())

    def test_query_parameter_spoofing_has_no_effect(self):
        """Passing user_id in query parameters cannot bypass ownership on deletion."""
        db = self.Session()
        conv = Conversation(id="conv_bob_safe", user_id="user_bob", title="Bob Safe")
        db.add(conv)
        db.commit()
        db.close()

        # Alice tries to delete Bob's conversation by appending ?user_id=user_bob
        app.dependency_overrides[get_current_user] = lambda: {"id": "user_alice", "email": "alice@example.com"}

        response = self.client.delete("/api/conversations/conv_bob_safe?user_id=user_bob")
        self.assertEqual(response.status_code, 403)

        db = self.Session()
        self.assertIsNotNone(db.query(Conversation).filter_by(id="conv_bob_safe").first())
        db.close()

    def test_history_listing_and_message_retrieval_reflect_deletion(self):
        """After deletion, conversation listing excludes it and message retrieval returns 404."""
        db = self.Session()
        conv1 = Conversation(id="conv_del_target", user_id="user_alice", title="To Delete")
        conv2 = Conversation(id="conv_keep", user_id="user_alice", title="To Keep")
        msg1 = Message(id="msg_in_target", conversation_id="conv_del_target", role="user", content="Hello")
        msg2 = Message(id="msg_in_keep", conversation_id="conv_keep", role="user", content="Stay")
        db.add_all([conv1, conv2, msg1, msg2])
        db.commit()
        db.close()

        app.dependency_overrides[get_current_user] = lambda: {"id": "user_alice", "email": "alice@example.com"}

        # Delete conv1
        del_res = self.client.delete("/api/conversations/conv_del_target")
        self.assertEqual(del_res.status_code, 200)

        # GET /api/conversations now only lists conv2
        list_res = self.client.get("/api/conversations")
        self.assertEqual(list_res.status_code, 200)
        items = list_res.json()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], "conv_keep")

        # GET /api/conversations/{conversation_id}/messages on deleted conversation returns 404
        msg_res = self.client.get("/api/conversations/conv_del_target/messages")
        self.assertEqual(msg_res.status_code, 404)

        # GET /api/conversations/{conversation_id}/messages on remaining conversation returns its message
        keep_msg_res = self.client.get("/api/conversations/conv_keep/messages")
        self.assertEqual(keep_msg_res.status_code, 200)
        self.assertEqual(len(keep_msg_res.json()), 1)
        self.assertEqual(keep_msg_res.json()[0]["content"], "Stay")


if __name__ == "__main__":
    unittest.main()
