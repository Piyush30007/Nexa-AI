"""
Unit and Integration Tests for Authenticated Conversation Persistence (Phase 6.2A)
==================================================================================
Verifies:
- Authenticated new conversation creates a Conversation record with user_id = clerk_user["id"]
- Authenticated existing conversation access succeeds when user_id matches
- Authenticated access to another user's conversation is rejected with HTTP 403
- Guest requests do not create a persistent database conversation
- Guest access to an authenticated user's conversation is rejected with HTTP 403
- Frontend-supplied user_id is ignored and cannot override verified Clerk identity
"""

import unittest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sqlalchemy.pool import StaticPool

from database import Base, Conversation, get_db
from app.services.conversation_service import resolve_or_create_conversation
from app.auth.clerk_auth import get_current_user_optional
from app.main import app


class TestConversationPersistenceUnit(unittest.TestCase):
    """Direct unit tests for resolve_or_create_conversation service."""

    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_authenticated_new_conversation_without_id(self):
        """Authenticated request without conversation_id creates a new Conversation with clerk user_id."""
        user = {"id": "user_clerk_123", "email": "user@example.com"}
        thread_id = resolve_or_create_conversation(self.db, conversation_id=None, current_user=user)

        self.assertIsNotNone(thread_id)
        conv = self.db.query(Conversation).filter_by(id=thread_id).first()
        self.assertIsNotNone(conv)
        self.assertEqual(conv.user_id, "user_clerk_123")
        self.assertEqual(conv.title, "New conversation")

    def test_authenticated_new_conversation_with_id(self):
        """Authenticated request with an unassigned conversation_id creates the record."""
        user = {"id": "user_clerk_123", "email": "user@example.com"}
        custom_id = "custom-conv-uuid-999"
        thread_id = resolve_or_create_conversation(self.db, conversation_id=custom_id, current_user=user)

        self.assertEqual(thread_id, custom_id)
        conv = self.db.query(Conversation).filter_by(id=custom_id).first()
        self.assertIsNotNone(conv)
        self.assertEqual(conv.user_id, "user_clerk_123")

    def test_authenticated_existing_own_conversation(self):
        """Authenticated request for own existing conversation succeeds."""
        user = {"id": "user_clerk_123", "email": "user@example.com"}
        conv = Conversation(id="my_conv_001", user_id="user_clerk_123", title="Prior Chat")
        self.db.add(conv)
        self.db.commit()

        thread_id = resolve_or_create_conversation(self.db, conversation_id="my_conv_001", current_user=user)
        self.assertEqual(thread_id, "my_conv_001")

    def test_authenticated_access_to_another_users_conversation_rejected(self):
        """Authenticated request for another user's conversation raises HTTP 403."""
        # Conv owned by user_alice
        conv = Conversation(id="alice_private_conv", user_id="user_alice", title="Alice's Chat")
        self.db.add(conv)
        self.db.commit()

        # Attacker user_bob
        bob = {"id": "user_bob", "email": "bob@example.com"}
        with self.assertRaises(HTTPException) as ctx:
            resolve_or_create_conversation(self.db, conversation_id="alice_private_conv", current_user=bob)

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("Forbidden", ctx.exception.detail)

    def test_guest_does_not_create_persistent_conversation(self):
        """Guest request creates no rows in conversations table and receives isolated UUID."""
        initial_count = self.db.query(Conversation).count()

        # Guest 1 without conversation_id receives a unique UUID
        thread_id_1 = resolve_or_create_conversation(self.db, conversation_id=None, current_user=None)
        self.assertIsNotNone(thread_id_1)
        self.assertNotEqual(thread_id_1, "default_user")
        self.assertEqual(len(thread_id_1), 36)  # valid UUID length
        self.assertEqual(self.db.query(Conversation).count(), initial_count)

        # Guest 2 without conversation_id receives a different unique UUID (thread isolation)
        thread_id_2 = resolve_or_create_conversation(self.db, conversation_id=None, current_user=None)
        self.assertNotEqual(thread_id_1, thread_id_2)
        self.assertEqual(self.db.query(Conversation).count(), initial_count)

        # Guest with a client-supplied ephemeral ID continues using that ID
        thread_id_custom = resolve_or_create_conversation(self.db, conversation_id="guest_temp_99", current_user=None)
        self.assertEqual(thread_id_custom, "guest_temp_99")
        self.assertEqual(self.db.query(Conversation).count(), initial_count)

    def test_guest_access_to_authenticated_conversation_rejected(self):
        """Guest attempting to supply an authenticated user's conversation_id is rejected with 403."""
        conv = Conversation(id="user_secret_conv", user_id="user_clerk_777", title="Secret")
        self.db.add(conv)
        self.db.commit()

        with self.assertRaises(HTTPException) as ctx:
            resolve_or_create_conversation(self.db, conversation_id="user_secret_conv", current_user=None)

        self.assertEqual(ctx.exception.status_code, 403)


class TestConversationEndpointIntegration(unittest.TestCase):
    """FastAPI integration tests for /api/chat with database persistence."""

    def setUp(self):
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

    @patch("app.main.guard", return_value=(False, ""))
    @patch("app.main.rag_agent.invoke")
    def test_authenticated_chat_creates_conversation(self, mock_rag, mock_guard):
        """Authenticated chat without conversation_id creates a Conversation record."""
        mock_rag.return_value = {
            "final_answer": "Company leave policy is 20 days.",
            "documents": [{"metadata": {"source": "policy.pdf", "page": 1}, "score": 0.95, "text": "20 days"}],
            "sufficient": True,
            "plan": ["Retrieve policy", "Generate answer"],
            "status": "completed",
        }

        user_info = {"id": "user_clerk_test_100", "email": "test@example.com"}
        app.dependency_overrides[get_current_user_optional] = lambda: user_info

        response = self.client.post(
            "/api/chat",
            json={"question": "What is the annual leave?"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("conversation_id", data)
        conv_id = data["conversation_id"]

        # Verify database record
        db = self.Session()
        conv = db.query(Conversation).filter_by(id=conv_id).first()
        db.close()

        self.assertIsNotNone(conv)
        self.assertEqual(conv.user_id, "user_clerk_test_100")
        self.assertEqual(data["answer"], "Company leave policy is 20 days.")
        self.assertTrue(data["grounded"])

    @patch("app.main.guard", return_value=(False, ""))
    @patch("app.main.rag_agent.invoke")
    def test_authenticated_chat_own_existing_conversation(self, mock_rag, mock_guard):
        """Authenticated chat continuing own conversation preserves conversation_id."""
        mock_rag.return_value = {
            "final_answer": "Working hours are 9 to 5.",
            "documents": [],
            "sufficient": False,
            "plan": [],
            "status": "completed",
        }

        # Pre-populate user conversation
        db = self.Session()
        conv = Conversation(id="existing_own_conv", user_id="user_clerk_test_200", title="Work Hours")
        db.add(conv)
        db.commit()
        db.close()

        user_info = {"id": "user_clerk_test_200", "email": "test2@example.com"}
        app.dependency_overrides[get_current_user_optional] = lambda: user_info

        response = self.client.post(
            "/api/chat",
            json={"question": "What are the hours?", "conversation_id": "existing_own_conv"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["conversation_id"], "existing_own_conv")

    def test_authenticated_chat_another_user_conversation_forbidden(self):
        """Authenticated chat targeting another user's conversation returns 403."""
        # Pre-populate victim's conversation
        db = self.Session()
        conv = Conversation(id="victim_conv_id", user_id="user_victim_999", title="Confidential")
        db.add(conv)
        db.commit()
        db.close()

        # Attacker authenticated session
        attacker_info = {"id": "user_attacker_000", "email": "attacker@example.com"}
        app.dependency_overrides[get_current_user_optional] = lambda: attacker_info

        response = self.client.post(
            "/api/chat",
            json={"question": "Give me the confidential details", "conversation_id": "victim_conv_id"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn("Forbidden", response.json()["detail"])

    @patch("app.main.guard", return_value=(False, ""))
    @patch("app.main.rag_agent.invoke")
    def test_guest_chat_preserves_behavior_no_db_conversation(self, mock_rag, mock_guard):
        """Guest chat creates no database record, returns unique UUID thread, and preserves isolation."""
        mock_rag.return_value = {
            "final_answer": "Guest response.",
            "documents": [],
            "sufficient": False,
            "plan": [],
            "status": "completed",
        }

        app.dependency_overrides[get_current_user_optional] = lambda: None

        db = self.Session()
        count_before = db.query(Conversation).count()
        db.close()

        # Guest request 1 without conversation_id
        response1 = self.client.post(
            "/api/chat",
            json={"question": "Hello as guest 1"},
        )
        self.assertEqual(response1.status_code, 200)
        data1 = response1.json()
        thread1 = data1["conversation_id"]
        self.assertNotEqual(thread1, "default_user")
        self.assertEqual(len(thread1), 36)

        # Guest request 2 without conversation_id -> gets distinct thread ID
        response2 = self.client.post(
            "/api/chat",
            json={"question": "Hello as guest 2"},
        )
        self.assertEqual(response2.status_code, 200)
        data2 = response2.json()
        thread2 = data2["conversation_id"]
        self.assertNotEqual(thread1, thread2)

        # Guest request 3 with provided conversation_id -> reuses provided thread ID
        response3 = self.client.post(
            "/api/chat",
            json={"question": "Continuing guest session", "conversation_id": thread1},
        )
        self.assertEqual(response3.status_code, 200)
        self.assertEqual(response3.json()["conversation_id"], thread1)

        # Verify zero persistent database rows were created for guests
        db = self.Session()
        count_after = db.query(Conversation).count()
        db.close()
        self.assertEqual(count_before, count_after)

    @patch("app.main.guard", return_value=(False, ""))
    @patch("app.main.rag_agent.invoke")
    def test_frontend_supplied_user_id_is_ignored(self, mock_rag, mock_guard):
        """Frontend passing a spoofed user_id in JSON payload cannot override verified Clerk user ID."""
        mock_rag.return_value = {
            "final_answer": "Spoof test answer.",
            "documents": [],
            "sufficient": False,
            "plan": [],
            "status": "completed",
        }

        verified_user = {"id": "user_clerk_verified_legit", "email": "legit@example.com"}
        app.dependency_overrides[get_current_user_optional] = lambda: verified_user

        # Payload includes spoofed user_id
        response = self.client.post(
            "/api/chat",
            json={
                "question": "Testing spoof immunity",
                "user_id": "spoofed_admin_hacker_id",
            },
        )

        self.assertEqual(response.status_code, 200)
        conv_id = response.json()["conversation_id"]

        # Check in database
        db = self.Session()
        conv = db.query(Conversation).filter_by(id=conv_id).first()
        db.close()

        self.assertIsNotNone(conv)
        self.assertEqual(conv.user_id, "user_clerk_verified_legit")
        self.assertNotEqual(conv.user_id, "spoofed_admin_hacker_id")


if __name__ == "__main__":
    unittest.main()
