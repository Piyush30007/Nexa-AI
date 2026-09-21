"""
Unit and Integration Tests for Authenticated Message Persistence (Phase 6.2B)
=============================================================================
Verifies:
- User question is persisted as Message(role="user")
- Assistant response is persisted as Message(role="assistant")
- RAG sources are properly preserved in Message.sources JSON
- Guest requests remain completely ephemeral (0 Conversation rows, 0 Message rows)
- Multiple conversation turns stay linked to the same conversation in order
- Cross-user access returns HTTP 403 and persists nothing
- Frontend user_id spoofing has no effect on stored records
- RAG failure cleans up pending user message to prevent orphaned partial turns
- Response contract remains intact
"""

import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, Conversation, Message, get_db
from app.auth.clerk_auth import get_current_user_optional
from app.main import app


class TestMessagePersistence(unittest.TestCase):

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

    @patch("app.main.guard", return_value=(False, ""))
    @patch("app.main.rag_agent.invoke")
    def test_authenticated_user_and_assistant_messages_persisted(self, mock_rag, mock_guard):
        """Authenticated chat persists both user question and assistant response with sources."""
        mock_sources = [
            {"chunk_id": "c1", "document": "handbook.pdf", "page": 4, "score": 0.88, "text": "20 days annual leave"}
        ]
        mock_rag.return_value = {
            "final_answer": "Employees receive 20 days paid leave.",
            "documents": [{"source": "handbook.pdf", "metadata": {"page": 4}, "score": 0.88, "content": "20 days annual leave"}],
            "sufficient": True,
            "plan": ["Retrieve leave policy", "Generate answer"],
            "status": "completed",
        }

        user_info = {"id": "user_clerk_alice", "email": "alice@example.com"}
        app.dependency_overrides[get_current_user_optional] = lambda: user_info

        response = self.client.post(
            "/api/chat",
            json={"question": "How many days of annual leave do I get?"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        conv_id = data["conversation_id"]
        self.assertEqual(data["answer"], "Employees receive 20 days paid leave.")
        self.assertTrue(data["grounded"])
        self.assertEqual(len(data["sources"]), 1)

        # Inspect DB state
        db = self.Session()
        conv = db.query(Conversation).filter_by(id=conv_id).first()
        self.assertIsNotNone(conv)
        self.assertEqual(conv.user_id, "user_clerk_alice")

        messages = db.query(Message).filter_by(conversation_id=conv_id).order_by(Message.created_at).all()
        self.assertEqual(len(messages), 2)

        # User message verification
        user_msg = messages[0]
        self.assertEqual(user_msg.role, "user")
        self.assertEqual(user_msg.content, "How many days of annual leave do I get?")
        self.assertEqual(user_msg.sources, [])

        # Assistant message verification
        asst_msg = messages[1]
        self.assertEqual(asst_msg.role, "assistant")
        self.assertEqual(asst_msg.content, "Employees receive 20 days paid leave.")
        self.assertEqual(len(asst_msg.sources), 1)
        self.assertEqual(asst_msg.sources[0]["document"], "handbook.pdf")
        self.assertEqual(asst_msg.sources[0]["page"], 4)

        db.close()

    @patch("app.main.guard", return_value=(False, ""))
    @patch("app.main.rag_agent.invoke")
    def test_guest_chat_persists_no_messages_or_conversations(self, mock_rag, mock_guard):
        """Guest requests must remain completely ephemeral with zero DB rows."""
        mock_rag.return_value = {
            "final_answer": "Public information response.",
            "documents": [],
            "sufficient": False,
            "plan": [],
            "status": "completed",
        }

        app.dependency_overrides[get_current_user_optional] = lambda: None

        response = self.client.post(
            "/api/chat",
            json={"question": "What is the public office address?"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNotNone(data["conversation_id"])

        # Check DB: absolutely zero rows in conversations or messages
        db = self.Session()
        self.assertEqual(db.query(Conversation).count(), 0)
        self.assertEqual(db.query(Message).count(), 0)
        db.close()

    @patch("app.main.guard", return_value=(False, ""))
    @patch("app.main.rag_agent.invoke")
    def test_multiple_turns_in_same_conversation(self, mock_rag, mock_guard):
        """Multiple conversational turns are stored under the same conversation in order."""
        mock_rag.side_effect = [
            {
                "final_answer": "Standard work hours are 9am - 5pm.",
                "documents": [],
                "sufficient": False,
                "plan": [],
                "status": "completed",
            },
            {
                "final_answer": "Yes, core collaboration hours are 10am - 3pm.",
                "documents": [],
                "sufficient": False,
                "plan": [],
                "status": "completed",
            },
        ]

        user_info = {"id": "user_clerk_multiturn", "email": "multi@example.com"}
        app.dependency_overrides[get_current_user_optional] = lambda: user_info

        # Turn 1: new conversation
        res1 = self.client.post("/api/chat", json={"question": "What are the work hours?"})
        self.assertEqual(res1.status_code, 200)
        conv_id = res1.json()["conversation_id"]

        # Turn 2: continue conversation
        res2 = self.client.post(
            "/api/chat",
            json={"question": "Are there core hours?", "conversation_id": conv_id},
        )
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json()["conversation_id"], conv_id)

        # Verify DB records
        db = self.Session()
        messages = db.query(Message).filter_by(conversation_id=conv_id).order_by(Message.created_at).all()
        self.assertEqual(len(messages), 4)
        roles = [m.role for m in messages]
        contents = [m.content for m in messages]

        self.assertEqual(roles, ["user", "assistant", "user", "assistant"])
        self.assertEqual(contents[0], "What are the work hours?")
        self.assertEqual(contents[1], "Standard work hours are 9am - 5pm.")
        self.assertEqual(contents[2], "Are there core hours?")
        self.assertEqual(contents[3], "Yes, core collaboration hours are 10am - 3pm.")
        db.close()

    def test_cross_user_access_rejected_and_no_messages_added(self):
        """Accessing another user's conversation returns 403 and persists no messages."""
        db = self.Session()
        alice_conv = Conversation(id="alice_conv_priv", user_id="user_alice", title="Alice")
        db.add(alice_conv)
        db.commit()
        db.close()

        bob_info = {"id": "user_bob", "email": "bob@example.com"}
        app.dependency_overrides[get_current_user_optional] = lambda: bob_info

        response = self.client.post(
            "/api/chat",
            json={"question": "Let me read your chat", "conversation_id": "alice_conv_priv"},
        )

        self.assertEqual(response.status_code, 403)

        # Ensure no messages were created
        db = self.Session()
        self.assertEqual(db.query(Message).count(), 0)
        db.close()

    @patch("app.main.guard", return_value=(False, ""))
    @patch("app.main.rag_agent.invoke")
    def test_frontend_user_id_spoofing_ignored_in_message_storage(self, mock_rag, mock_guard):
        """Frontend passing a spoofed user_id in JSON payload cannot hijack conversation or messages."""
        mock_rag.return_value = {
            "final_answer": "Verified identity answer.",
            "documents": [],
            "sufficient": False,
            "plan": [],
            "status": "completed",
        }

        user_info = {"id": "user_real_verified", "email": "real@example.com"}
        app.dependency_overrides[get_current_user_optional] = lambda: user_info

        response = self.client.post(
            "/api/chat",
            json={
                "question": "Can I spoof?",
                "user_id": "malicious_spoofed_admin",
            },
        )

        self.assertEqual(response.status_code, 200)
        conv_id = response.json()["conversation_id"]

        db = self.Session()
        conv = db.query(Conversation).filter_by(id=conv_id).first()
        self.assertEqual(conv.user_id, "user_real_verified")
        self.assertNotEqual(conv.user_id, "malicious_spoofed_admin")

        messages = db.query(Message).filter_by(conversation_id=conv_id).all()
        self.assertEqual(len(messages), 2)
        db.close()

    @patch("app.main.guard", return_value=(True, "Safety policy blocked this query."))
    def test_guardrails_blocked_request_persists_refusal(self, mock_guard):
        """When guardrails block a query, user query and refusal assistant response are recorded."""
        user_info = {"id": "user_guard_test", "email": "guard@example.com"}
        app.dependency_overrides[get_current_user_optional] = lambda: user_info

        response = self.client.post(
            "/api/chat",
            json={"question": "Dangerous query"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["answer"], "Safety policy blocked this query.")
        conv_id = data["conversation_id"]

        db = self.Session()
        messages = db.query(Message).filter_by(conversation_id=conv_id).order_by(Message.created_at).all()
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].role, "user")
        self.assertEqual(messages[0].content, "Dangerous query")
        self.assertEqual(messages[1].role, "assistant")
        self.assertEqual(messages[1].content, "Safety policy blocked this query.")
        self.assertEqual(messages[1].sources, [])
        db.close()

    @patch("app.main.guard", return_value=(False, ""))
    @patch("app.main.rag_agent.invoke", side_effect=RuntimeError("LangGraph execution failure"))
    def test_rag_failure_cleans_up_pending_user_message(self, mock_rag, mock_guard):
        """If RAG fails unexpectedly, the pending user message is cleaned up to prevent partial state."""
        user_info = {"id": "user_rag_fail", "email": "fail@example.com"}
        app.dependency_overrides[get_current_user_optional] = lambda: user_info

        response = self.client.post(
            "/api/chat",
            json={"question": "This query triggers a failure"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "error")

        # Incomplete turn is not persisted: 0 messages in database
        db = self.Session()
        messages = db.query(Message).all()
        self.assertEqual(len(messages), 0)
        db.close()


if __name__ == "__main__":
    unittest.main()
