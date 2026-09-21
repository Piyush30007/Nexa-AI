"""
Unit and Integration Tests for Authenticated Conversation Messages Retrieval (Phase 6.3B)
========================================================================================
Verifies:
- Authenticated user can retrieve messages from their own conversation
- Messages are returned chronologically (oldest -> newest: created_at ASC, id ASC)
- Assistant source metadata is preserved accurately
- Another authenticated user cannot retrieve the conversation's messages (403 Forbidden)
- Missing or invalid authentication returns HTTP 401
- Guest/unassigned conversation (user_id IS NULL) cannot be retrieved (403 Forbidden)
- Nonexistent conversation returns HTTP 404 Not Found
- Empty owned conversation returns HTTP 200 with []
- user_id query parameter spoofing has no effect
- Existing GET /api/conversations behavior remains intact
"""

import unittest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, Conversation, Message, get_db
from app.auth.clerk_auth import get_current_user
from app.main import app


class TestConversationMessages(unittest.TestCase):

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

    def test_authenticated_user_retrieves_own_messages_ordered_and_with_sources(self):
        """Authenticated user can retrieve messages from their own conversation oldest -> newest with sources."""
        db = self.Session()
        now = datetime(2026, 9, 19, 10, 0, 0, tzinfo=timezone.utc)

        conv = Conversation(id="conv_alice_1", user_id="user_alice", title="Leave Chat", created_at=now)

        msg1 = Message(
            id="msg_001",
            conversation_id="conv_alice_1",
            role="user",
            content="How many days of leave do I get?",
            sources=[],
            created_at=now + timedelta(seconds=1),
        )
        msg2 = Message(
            id="msg_002",
            conversation_id="conv_alice_1",
            role="assistant",
            content="Employees receive 20 days paid leave.",
            sources=[{"chunk_id": "c1", "document": "handbook.pdf", "page": 4, "score": 0.95}],
            created_at=now + timedelta(seconds=2),
        )
        msg3 = Message(
            id="msg_003",
            conversation_id="conv_alice_1",
            role="user",
            content="Can I carry over unused days?",
            sources=[],
            created_at=now + timedelta(seconds=10),
        )
        db.add_all([conv, msg1, msg2, msg3])
        db.commit()
        db.close()

        app.dependency_overrides[get_current_user] = lambda: {"id": "user_alice", "email": "alice@example.com"}

        response = self.client.get("/api/conversations/conv_alice_1/messages")
        self.assertEqual(response.status_code, 200)
        messages = response.json()

        self.assertEqual(len(messages), 3)

        # Chronological order verification: msg1 -> msg2 -> msg3
        self.assertEqual([m["id"] for m in messages], ["msg_001", "msg_002", "msg_003"])
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"], "How many days of leave do I get?")
        self.assertEqual(messages[0]["sources"], [])

        self.assertEqual(messages[1]["role"], "assistant")
        self.assertEqual(messages[1]["content"], "Employees receive 20 days paid leave.")
        self.assertEqual(len(messages[1]["sources"]), 1)
        self.assertEqual(messages[1]["sources"][0]["document"], "handbook.pdf")
        self.assertEqual(messages[1]["sources"][0]["page"], 4)
        self.assertEqual(messages[1]["sources"][0]["score"], 0.95)

        self.assertEqual(messages[2]["role"], "user")
        self.assertEqual(messages[2]["content"], "Can I carry over unused days?")

    def test_cross_user_message_retrieval_forbidden(self):
        """Another authenticated user cannot retrieve messages from a conversation they do not own."""
        db = self.Session()
        conv = Conversation(id="conv_alice_priv", user_id="user_alice", title="Alice Private")
        msg = Message(id="msg_a", conversation_id="conv_alice_priv", role="user", content="Secret")
        db.add_all([conv, msg])
        db.commit()
        db.close()

        # Attacker user_bob
        app.dependency_overrides[get_current_user] = lambda: {"id": "user_bob", "email": "bob@example.com"}

        response = self.client.get("/api/conversations/conv_alice_priv/messages")
        self.assertEqual(response.status_code, 403)
        self.assertIn("Forbidden", response.json()["detail"])

    def test_missing_authentication_returns_401(self):
        """Unauthenticated requests must return HTTP 401."""
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]

        response = self.client.get("/api/conversations/any_conv/messages")
        self.assertEqual(response.status_code, 401)

    def test_guest_conversation_cannot_be_retrieved(self):
        """Guest/unassigned conversations with user_id=NULL cannot be retrieved."""
        db = self.Session()
        conv = Conversation(id="conv_guest_ephem", user_id=None, title="Guest Chat")
        msg = Message(id="msg_g", conversation_id="conv_guest_ephem", role="user", content="Guest Msg")
        db.add_all([conv, msg])
        db.commit()
        db.close()

        app.dependency_overrides[get_current_user] = lambda: {"id": "user_alice", "email": "alice@example.com"}

        response = self.client.get("/api/conversations/conv_guest_ephem/messages")
        self.assertEqual(response.status_code, 403)

    def test_nonexistent_conversation_returns_404(self):
        """Requesting messages for a nonexistent conversation returns HTTP 404."""
        app.dependency_overrides[get_current_user] = lambda: {"id": "user_alice", "email": "alice@example.com"}

        response = self.client.get("/api/conversations/nonexistent_uuid_999/messages")
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"].lower())

    def test_empty_owned_conversation_returns_empty_list(self):
        """An owned conversation with no messages returns HTTP 200 with []."""
        db = self.Session()
        conv = Conversation(id="conv_empty_1", user_id="user_alice", title="Empty Chat")
        db.add(conv)
        db.commit()
        db.close()

        app.dependency_overrides[get_current_user] = lambda: {"id": "user_alice", "email": "alice@example.com"}

        response = self.client.get("/api/conversations/conv_empty_1/messages")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_query_parameter_spoofing_ignored(self):
        """Passing user_id in query parameters cannot bypass ownership checks."""
        db = self.Session()
        conv = Conversation(id="conv_bob_priv", user_id="user_bob", title="Bob Private")
        msg = Message(id="msg_b", conversation_id="conv_bob_priv", role="user", content="Bob's notes")
        db.add_all([conv, msg])
        db.commit()
        db.close()

        # Alice attempts to query Bob's conversation pretending to be Bob via query param
        app.dependency_overrides[get_current_user] = lambda: {"id": "user_alice", "email": "alice@example.com"}

        response = self.client.get("/api/conversations/conv_bob_priv/messages?user_id=user_bob")
        self.assertEqual(response.status_code, 403)

    def test_deterministic_ordering_tiebreaker(self):
        """Messages with identical created_at timestamps are deterministically ordered by id ASC."""
        db = self.Session()
        same_time = datetime(2026, 9, 19, 12, 0, 0, tzinfo=timezone.utc)
        conv = Conversation(id="conv_tie", user_id="user_alice", title="Tie")

        # Insert out-of-order id
        msg_z = Message(id="msg_z", conversation_id="conv_tie", role="user", content="Z", created_at=same_time)
        msg_a = Message(id="msg_a", conversation_id="conv_tie", role="assistant", content="A", created_at=same_time)

        db.add_all([conv, msg_z, msg_a])
        db.commit()
        db.close()

        app.dependency_overrides[get_current_user] = lambda: {"id": "user_alice", "email": "alice@example.com"}

        response = self.client.get("/api/conversations/conv_tie/messages")
        self.assertEqual(response.status_code, 200)
        ids = [m["id"] for m in response.json()]
        self.assertEqual(ids, ["msg_a", "msg_z"])

    def test_existing_conversations_listing_endpoint_unchanged(self):
        """GET /api/conversations continues to return the conversation list correctly."""
        db = self.Session()
        conv = Conversation(id="conv_list_check", user_id="user_alice", title="Listing Check")
        db.add(conv)
        db.commit()
        db.close()

        app.dependency_overrides[get_current_user] = lambda: {"id": "user_alice", "email": "alice@example.com"}

        response = self.client.get("/api/conversations")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["id"], "conv_list_check")


if __name__ == "__main__":
    unittest.main()
