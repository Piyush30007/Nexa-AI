"""
Unit Tests for Nexa AI Enterprise Conversation Model (Phase 6.1)
================================================================
Verifies:
- Conversation model contains nullable user_id with index
- user_id can be NULL (for guest chats)
- user_id can contain a Clerk user ID
- Conversation -> Message relationship and cascade deletion remain intact
"""

import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, Conversation, Message


class TestConversationModel(unittest.TestCase):

    def setUp(self):
        # Create an isolated in-memory SQLite database for model testing
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_conversation_model_schema_attributes(self):
        """Verify user_id column definition on Conversation model."""
        columns = Conversation.__table__.columns
        self.assertIn("user_id", columns)
        user_id_col = columns["user_id"]

        self.assertTrue(user_id_col.nullable, "user_id must be nullable for guest users")
        self.assertTrue(user_id_col.index, "user_id should be indexed for efficient user query filtering")

    def test_user_id_can_be_null_for_guest(self):
        """Guest conversations have user_id = NULL."""
        conv = Conversation(
            id="conv_guest_001",
            title="Guest Conversation",
            user_id=None,
        )
        self.db.add(conv)
        self.db.commit()

        retrieved = self.db.query(Conversation).filter_by(id="conv_guest_001").first()
        self.assertIsNotNone(retrieved)
        self.assertIsNone(retrieved.user_id)
        self.assertEqual(retrieved.title, "Guest Conversation")

    def test_user_id_can_store_clerk_user_id(self):
        """Authenticated conversations store the Clerk user ID."""
        clerk_id = "user_29w83sxm10pq"
        conv = Conversation(
            id="conv_auth_002",
            title="Clerk User Chat",
            user_id=clerk_id,
        )
        self.db.add(conv)
        self.db.commit()

        retrieved = self.db.query(Conversation).filter_by(user_id=clerk_id).first()
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, "conv_auth_002")
        self.assertEqual(retrieved.user_id, clerk_id)

    def test_conversation_message_relationship_intact(self):
        """Conversation -> Message relationship and cascade deletion remain intact."""
        conv = Conversation(
            id="conv_rel_003",
            title="Relationship Test",
            user_id="user_clerk_test",
        )
        msg1 = Message(
            id="msg_001",
            conversation_id="conv_rel_003",
            role="user",
            content="What is the leave policy?",
            sources=[],
        )
        msg2 = Message(
            id="msg_002",
            conversation_id="conv_rel_003",
            role="assistant",
            content="Employees receive 20 days paid leave.",
            sources=[{"document": "policy.pdf", "page": 1}],
        )
        self.db.add_all([conv, msg1, msg2])
        self.db.commit()

        # Check relationship from Conversation side
        retrieved_conv = self.db.query(Conversation).filter_by(id="conv_rel_003").first()
        self.assertEqual(len(retrieved_conv.messages), 2)
        self.assertEqual(retrieved_conv.messages[0].role, "user")

        # Check relationship from Message side
        retrieved_msg = self.db.query(Message).filter_by(id="msg_001").first()
        self.assertEqual(retrieved_msg.conversation.user_id, "user_clerk_test")

        # Check cascade deletion
        self.db.delete(retrieved_conv)
        self.db.commit()

        remaining_messages = self.db.query(Message).filter_by(conversation_id="conv_rel_003").all()
        self.assertEqual(len(remaining_messages), 0, "Messages must cascade delete with conversation")


if __name__ == "__main__":
    unittest.main()
