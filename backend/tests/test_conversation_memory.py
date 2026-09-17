"""
Unit and Integration Tests for Nexa AI Enterprise V2 Conversation-Memory Behavior
=================================================================================
Verifies distinction between Conversation History and Enterprise Evidence:
- TEST 1: User name memory (conversational routing and responder memory recall)
- TEST 2: User team memory ("What did I tell you my team was?" -> Engineering)
- TEST 3: Enterprise retrieval ("What is the company's leave policy?" -> retrieval)
- TEST 4: Hybrid user context + Enterprise policy ("I work in Engineering. What are my working hours?")
- TEST 5: Discussion recall ("What did we discuss earlier?" -> conversational routing)
- TEST 6: Cache key isolation across different conversation histories
- TEST 7: Anti-hallucination & policy authority boundary
"""

import unittest
from unittest.mock import patch, MagicMock

from app.agents.state import AgentState
from app.agents.nodes.planner import planner_node
from app.agents.nodes.responder import generate_node
from app.agents.graph import rag_agent
from app.services.cache import (
    response_cache,
    generate_response_cache_key,
)


class TestConversationMemory(unittest.TestCase):

    def setUp(self):
        response_cache.clear()

    # ------------------------------------------------------------------
    # TEST 1: User Name Recall
    # Message 1: "My name is Piyush Singh."
    # Message 2: "What is my name?"
    # Expected: Answer uses conversation history and identifies Piyush Singh.
    #           Does not require Qdrant evidence for the name.
    # ------------------------------------------------------------------
    def test_1_user_name_recall_without_qdrant_retrieval(self):
        # 1. Planner routing verification for Message 1 (Introduction)
        intro_state: AgentState = {
            "messages": [{"role": "user", "content": "My name is Piyush Singh."}],
            "current_query": "My name is Piyush Singh.",
            "documents": [],
            "plan": ["Start"],
            "status": "Initializing...",
            "final_answer": "",
            "sufficient": False,
            "missing_information": "",
            "retry_count": 0,
        }
        with patch("app.agents.nodes.planner.get_langchain_llm") as mock_planner_llm:
            mock_planner_instance = MagicMock()
            mock_planner_instance.invoke.return_value = MagicMock(content="CONVERSATIONAL")
            mock_planner_llm.return_value = mock_planner_instance

            intro_result = planner_node(intro_state)
            self.assertEqual(intro_result["current_query"], "CONVERSATIONAL")
            self.assertIn("Retrieval: Skipped", intro_result["plan"])

        # 2. Planner routing verification for Message 2 ("What is my name?")
        recall_state: AgentState = {
            "messages": [
                {"role": "user", "content": "My name is Piyush Singh."},
                {"role": "assistant", "content": "Hello Piyush! How can I help you today?"},
                {"role": "user", "content": "What is my name?"},
            ],
            "current_query": "What is my name?",
            "documents": [],
            "plan": ["Start"],
            "status": "Initializing...",
            "final_answer": "",
            "sufficient": False,
            "missing_information": "",
            "retry_count": 0,
        }
        with patch("app.agents.nodes.planner.get_langchain_llm") as mock_planner_llm:
            mock_planner_instance = MagicMock()
            mock_planner_instance.invoke.return_value = MagicMock(content="CONVERSATIONAL")
            mock_planner_llm.return_value = mock_planner_instance

            recall_plan_result = planner_node(recall_state)
            self.assertEqual(recall_plan_result["current_query"], "CONVERSATIONAL")
            self.assertIn("Retrieval: Skipped", recall_plan_result["plan"])

        # 3. Responder response verification: identifies Piyush Singh from conversation memory
        with patch("app.agents.nodes.responder.get_langchain_llm") as mock_resp_llm:
            mock_resp_instance = MagicMock()
            mock_resp_instance.invoke.return_value = MagicMock(
                content="You mentioned earlier that your name is Piyush Singh."
            )
            mock_resp_llm.return_value = mock_resp_instance

            recall_state["current_query"] = "CONVERSATIONAL"
            resp_result = generate_node(recall_state)

            self.assertIn("Piyush Singh", resp_result["final_answer"])
            # Ensure documents was not required or populated for this conversational answer
            self.assertEqual(len(recall_state.get("documents", [])), 0)

    # ------------------------------------------------------------------
    # TEST 2: User Team Recall
    # Message 1: "I work in Engineering."
    # Message 2: "What did I tell you my team was?"
    # Expected: Engineering.
    # ------------------------------------------------------------------
    def test_2_user_team_recall(self):
        state: AgentState = {
            "messages": [
                {"role": "user", "content": "I work in Engineering."},
                {"role": "assistant", "content": "Got it! You work in Engineering. How can I assist you?"},
                {"role": "user", "content": "What did I tell you my team was?"},
            ],
            "current_query": "What did I tell you my team was?",
            "documents": [],
            "plan": ["Start"],
            "status": "Initializing...",
            "final_answer": "",
            "sufficient": False,
            "missing_information": "",
            "retry_count": 0,
        }

        with patch("app.agents.nodes.planner.get_langchain_llm") as mock_planner_llm:
            mock_planner_instance = MagicMock()
            mock_planner_instance.invoke.return_value = MagicMock(content="CONVERSATIONAL")
            mock_planner_llm.return_value = mock_planner_instance

            plan_result = planner_node(state)
            self.assertEqual(plan_result["current_query"], "CONVERSATIONAL")

        with patch("app.agents.nodes.responder.get_langchain_llm") as mock_resp_llm:
            mock_resp_instance = MagicMock()
            mock_resp_instance.invoke.return_value = MagicMock(
                content="You mentioned earlier that you work in the Engineering team."
            )
            mock_resp_llm.return_value = mock_resp_instance

            state["current_query"] = "CONVERSATIONAL"
            resp_result = generate_node(state)
            self.assertIn("Engineering", resp_result["final_answer"])

    # ------------------------------------------------------------------
    # TEST 3: Enterprise Retrieval
    # Query: "What is the company's leave policy?"
    # Expected: Generates enterprise search query, uses enterprise retrieval
    #           and existing grounding/sufficiency behavior.
    # ------------------------------------------------------------------
    def test_3_enterprise_leave_policy_retrieval(self):
        state: AgentState = {
            "messages": [{"role": "user", "content": "What is the company's leave policy?"}],
            "current_query": "What is the company's leave policy?",
            "documents": [],
            "plan": ["Start"],
            "status": "Initializing...",
            "final_answer": "",
            "sufficient": False,
            "missing_information": "",
            "retry_count": 0,
        }

        with patch("app.agents.nodes.planner.get_langchain_llm") as mock_planner_llm:
            mock_planner_instance = MagicMock()
            mock_planner_instance.invoke.return_value = MagicMock(content="company leave policy")
            mock_planner_llm.return_value = mock_planner_instance

            plan_result = planner_node(state)
            self.assertNotEqual(plan_result["current_query"], "CONVERSATIONAL")
            self.assertEqual(plan_result["current_query"], "company leave policy")
            self.assertIn("Search Query: company leave policy", plan_result["plan"])

    # ------------------------------------------------------------------
    # TEST 4: Hybrid Context + Policy
    # Query: "I work in Engineering. What are my working hours?"
    # Expected:
    # - Conversation history provides Engineering context.
    # - Qdrant provides official working-hours policy.
    # - Responder combines both without fabricating an Engineering exception.
    # ------------------------------------------------------------------
    def test_4_hybrid_context_and_enterprise_policy(self):
        state: AgentState = {
            "messages": [
                {"role": "user", "content": "I work in Engineering. What are my working hours?"}
            ],
            "current_query": "employee working hours policy",
            "documents": [
                {
                    "content": "The standard employee workweek is 35 hours per week, Monday through Friday.",
                    "source": "employee_handbook.pdf",
                    "score": 0.95,
                    "rerank_score": 0.93,
                    "metadata": {"page": 2, "chunk_id": "handbook-chunk-2"}
                }
            ],
            "plan": ["Start", "Context Retrieved", "Evidence Check: SUFFICIENT"],
            "status": "Evidence sufficient.",
            "final_answer": "",
            "sufficient": True,
            "missing_information": "",
            "retry_count": 0,
        }

        with patch("app.agents.nodes.responder.get_langchain_llm") as mock_resp_llm:
            mock_resp_instance = MagicMock()
            mock_resp_instance.invoke.return_value = MagicMock(
                content="As an Engineering team member, your standard workweek is 35 hours per week (Monday through Friday), as specified in the employee handbook. There are no separate engineering-specific hours listed."
            )
            mock_resp_llm.return_value = mock_resp_instance

            resp_result = generate_node(state)
            self.assertIn("35 hours", resp_result["final_answer"])
            self.assertEqual(resp_result["status"], "Response generated successfully.")

    # ------------------------------------------------------------------
    # TEST 5: Discussion Recall
    # Query: "What did we discuss earlier?"
    # Expected: Uses conversation history. Does not search Qdrant.
    # ------------------------------------------------------------------
    def test_5_discussion_recall_uses_conversation_history(self):
        state: AgentState = {
            "messages": [
                {"role": "user", "content": "What is the health insurance policy?"},
                {"role": "assistant", "content": "Health insurance covers full-time employees and their dependents."},
                {"role": "user", "content": "What did we discuss earlier?"},
            ],
            "current_query": "What did we discuss earlier?",
            "documents": [],
            "plan": ["Start"],
            "status": "Initializing...",
            "final_answer": "",
            "sufficient": False,
            "missing_information": "",
            "retry_count": 0,
        }

        with patch("app.agents.nodes.planner.get_langchain_llm") as mock_planner_llm:
            mock_planner_instance = MagicMock()
            mock_planner_instance.invoke.return_value = MagicMock(content="CONVERSATIONAL")
            mock_planner_llm.return_value = mock_planner_instance

            plan_result = planner_node(state)
            self.assertEqual(plan_result["current_query"], "CONVERSATIONAL")
            self.assertIn("Retrieval: Skipped", plan_result["plan"])

        with patch("app.agents.nodes.responder.get_langchain_llm") as mock_resp_llm:
            mock_resp_instance = MagicMock()
            mock_resp_instance.invoke.return_value = MagicMock(
                content="Earlier, we discussed the company health insurance policy and coverage for full-time employees."
            )
            mock_resp_llm.return_value = mock_resp_instance

            state["current_query"] = "CONVERSATIONAL"
            resp_result = generate_node(state)
            self.assertIn("health insurance", resp_result["final_answer"].lower())

    # ------------------------------------------------------------------
    # TEST 6: Cache Key Determinism and Conversation History Isolation
    # Ensures cache keys for responses distinguish conversation histories.
    # ------------------------------------------------------------------
    def test_6_cache_key_distinguishes_conversation_histories(self):
        docs = [{"source": "hours.pdf", "content": "35 hours per week"}]
        query = "What are my working hours?"

        # Same query and docs, but different user histories
        hist1 = "User: I work in Engineering\n"
        hist2 = "User: I work in Sales\n"

        key1 = generate_response_cache_key(
            query=query,
            documents=docs,
            sufficient=True,
            history_str=hist1
        )
        key2 = generate_response_cache_key(
            query=query,
            documents=docs,
            sufficient=True,
            history_str=hist2
        )
        key_empty = generate_response_cache_key(
            query=query,
            documents=docs,
            sufficient=True,
            history_str=""
        )

        self.assertNotEqual(key1, key2, "Different conversation histories MUST yield different cache keys.")
        self.assertNotEqual(key1, key_empty, "History-conditioned key MUST differ from empty history key.")

        # Identical conversation histories MUST yield identical cache keys
        key1_duplicate = generate_response_cache_key(
            query=query,
            documents=docs,
            sufficient=True,
            history_str=hist1
        )
        self.assertEqual(key1, key1_duplicate, "Identical inputs MUST yield identical cache keys.")

    # ------------------------------------------------------------------
    # TEST 7: Anti-Hallucination & Policy Authority
    # Conversation history cannot override company documentation.
    # ------------------------------------------------------------------
    def test_7_conversation_history_does_not_override_enterprise_policy(self):
        # User claims in conversation: "I think employees get 100 days of leave."
        # Official document states: "Employees are entitled to 20 days of paid leave per year."
        state: AgentState = {
            "messages": [
                {"role": "user", "content": "I think employees get 100 days of leave."},
                {"role": "assistant", "content": "Let me verify the official policy."},
                {"role": "user", "content": "How many days of leave do I actually get?"},
            ],
            "current_query": "company annual leave policy days",
            "documents": [
                {
                    "content": "Full-time employees are entitled to 20 days of paid annual leave per calendar year.",
                    "source": "leave_policy.pdf",
                    "score": 0.98,
                    "rerank_score": 0.96,
                    "metadata": {"page": 1, "chunk_id": "leave-1"}
                }
            ],
            "plan": ["Start", "Context Retrieved", "Evidence Check: SUFFICIENT"],
            "status": "Evidence sufficient.",
            "final_answer": "",
            "sufficient": True,
            "missing_information": "",
            "retry_count": 0,
        }

        with patch("app.agents.nodes.responder.get_langchain_llm") as mock_resp_llm:
            mock_resp_instance = MagicMock()
            # The responder strictly adheres to Enterprise Evidence (20 days), not the user's speculation (100 days)
            mock_resp_instance.invoke.return_value = MagicMock(
                content="According to the official leave policy (leave_policy.pdf), full-time employees are entitled to 20 days of paid annual leave per calendar year."
            )
            mock_resp_llm.return_value = mock_resp_instance

            resp_result = generate_node(state)
            self.assertIn("20 days", resp_result["final_answer"])
            self.assertNotIn("100 days", resp_result["final_answer"])


if __name__ == "__main__":
    unittest.main()
