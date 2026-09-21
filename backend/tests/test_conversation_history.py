"""
Unit and Integration Tests for Authenticated Conversation History Listing (Phase 6.3A)
======================================================================================
Verifies:
- Authenticated user receives their own conversations
- Conversations belonging to another user are excluded
- Guest/unassigned conversations (user_id IS NULL) are excluded
- User with no conversations receives HTTP 200 with []
- Missing or invalid authentication returns HTTP 401
- user_id query parameter spoofing does not affect results
- Ordering is deterministic, newest first (created_at DESC, id DESC)
- Response schema contains only {"id", "title", "created_at"}
"""

import unittest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, Conversation, get_db
from app.auth.clerk_auth import get_current_user
from app.main import app


class TestConversationHistory(unittest.TestCase):

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

    def test_authenticated_user_receives_own_conversations_only(self):
        """Authenticated user receives all and only their own conversations."""
        db = self.Session()
        now = datetime.now(timezone.utc)
        # Alice's conversations
        conv_a1 = Conversation(id="conv_alice_1", user_id="user_alice", title="Alice Chat 1", created_at=now)
        conv_a2 = Conversation(id="conv_alice_2", user_id="user_alice", title="Alice Chat 2", created_at=now + timedelta(seconds=10))
        # Bob's conversation
        conv_b1 = Conversation(id="conv_bob_1", user_id="user_bob", title="Bob Chat 1", created_at=now + timedelta(seconds=20))
        db.add_all([conv_a1, conv_a2, conv_b1])
        db.commit()
        db.close()

        # Alice's authenticated session
        app.dependency_overrides[get_current_user] = lambda: {"id": "user_alice", "email": "alice@example.com"}

        response = self.client.get("/api/conversations")
        self.assertEqual(response.status_code, 200)
        items = response.json()

        self.assertEqual(len(items), 2)
        returned_ids = [item["id"] for item in items]
        self.assertIn("conv_alice_1", returned_ids)
        self.assertIn("conv_alice_2", returned_ids)
        self.assertNotIn("conv_bob_1", returned_ids)

    def test_guest_conversations_excluded(self):
        """Guest/unassigned conversations with user_id = NULL are never returned."""
        db = self.Session()
        now = datetime.now(timezone.utc)
        conv_user = Conversation(id="conv_user_1", user_id="user_charlie", title="User Chat", created_at=now)
        conv_guest = Conversation(id="conv_guest_1", user_id=None, title="Guest Chat", created_at=now + timedelta(seconds=5))
        db.add_all([conv_user, conv_guest])
        db.commit()
        db.close()

        app.dependency_overrides[get_current_user] = lambda: {"id": "user_charlie", "email": "charlie@example.com"}

        response = self.client.get("/api/conversations")
        self.assertEqual(response.status_code, 200)
        items = response.json()

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], "conv_user_1")
        self.assertEqual(items[0]["title"], "User Chat")

    def test_empty_history_returns_empty_list(self):
        """User with no conversations receives HTTP 200 with an empty list []."""
        app.dependency_overrides[get_current_user] = lambda: {"id": "user_new", "email": "new@example.com"}

        response = self.client.get("/api/conversations")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_missing_authentication_returns_401(self):
        """Request without valid authentication returns HTTP 401."""
        # Ensure no get_current_user override
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]

        # 1. No Authorization header
        response = self.client.get("/api/conversations")
        self.assertEqual(response.status_code, 401)
        self.assertIn("Authentication required", response.json()["detail"])

        # 2. Malformed Authorization header
        response_malformed = self.client.get("/api/conversations", headers={"Authorization": "Basic 12345"})
        self.assertEqual(response_malformed.status_code, 401)

    def test_query_parameter_spoofing_ignored(self):
        """Passing user_id in query parameters has zero effect on retrieved conversations."""
        db = self.Session()
        now = datetime.now(timezone.utc)
        conv_alice = Conversation(id="conv_alice_secret", user_id="user_alice", title="Alice", created_at=now)
        conv_victim = Conversation(id="conv_victim_target", user_id="user_victim", title="Victim", created_at=now)
        db.add_all([conv_alice, conv_victim])
        db.commit()
        db.close()

        # Alice attempts to spoof victim in query params
        app.dependency_overrides[get_current_user] = lambda: {"id": "user_alice", "email": "alice@example.com"}

        response = self.client.get("/api/conversations?user_id=user_victim")
        self.assertEqual(response.status_code, 200)
        items = response.json()

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], "conv_alice_secret")
        self.assertNotEqual(items[0]["id"], "conv_victim_target")

    def test_ordering_newest_first_with_deterministic_tiebreaker(self):
        """Conversations are ordered by created_at DESC, with id DESC as tiebreaker."""
        db = self.Session()
        base_time = datetime(2026, 9, 19, 12, 0, 0, tzinfo=timezone.utc)

        conv1 = Conversation(id="conv_old", user_id="user_order", title="Old Chat", created_at=base_time)
        conv2 = Conversation(id="conv_new", user_id="user_order", title="New Chat", created_at=base_time + timedelta(hours=1))
        # Two conversations sharing identical timestamp
        conv_tie_a = Conversation(id="conv_tie_a", user_id="user_order", title="Tie A", created_at=base_time + timedelta(hours=2))
        conv_tie_z = Conversation(id="conv_tie_z", user_id="user_order", title="Tie Z", created_at=base_time + timedelta(hours=2))

        db.add_all([conv1, conv2, conv_tie_a, conv_tie_z])
        db.commit()
        db.close()

        app.dependency_overrides[get_current_user] = lambda: {"id": "user_order", "email": "order@example.com"}

        response = self.client.get("/api/conversations")
        self.assertEqual(response.status_code, 200)
        items = response.json()

        returned_ids = [item["id"] for item in items]
        # Newer timestamps come first; tiebreaker conv_tie_z comes before conv_tie_a
        self.assertEqual(returned_ids, ["conv_tie_z", "conv_tie_a", "conv_new", "conv_old"])

    def test_response_schema_exact_fields(self):
        """Each conversation item contains only the fields needed for history listing."""
        db = self.Session()
        conv = Conversation(id="conv_schema_check", user_id="user_schema", title="Schema Check")
        db.add(conv)
        db.commit()
        db.close()

        app.dependency_overrides[get_current_user] = lambda: {"id": "user_schema", "email": "schema@example.com"}

        response = self.client.get("/api/conversations")
        self.assertEqual(response.status_code, 200)
        items = response.json()

        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(set(item.keys()), {"id", "title", "created_at"})
        self.assertEqual(item["id"], "conv_schema_check")
        self.assertEqual(item["title"], "Schema Check")
        self.assertIsInstance(item["created_at"], str)


if __name__ == "__main__":
    unittest.main()
