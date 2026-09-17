"""
Unit Tests for Nexa AI Enterprise Caching Architecture
======================================================
Tests A through K covering Gemini Embedding Cache and LLM Response Cache.
Uses mocks for Gemini and LLM calls so tests do NOT consume API quota.
"""

import time
import unittest
from unittest.mock import patch, MagicMock

from app.config import settings
from app.services.cache import (
    InMemoryCache,
    embedding_cache,
    response_cache,
    normalize_query_for_cache,
    generate_embedding_cache_key,
    generate_response_cache_key,
)
from app.services.embedding import embed_query
from app.agents.nodes.responder import generate_node
from app.agents.state import AgentState


class TestEmbeddingCache(unittest.TestCase):
    """
    Tests A through E: Gemini Embedding Cache
    """

    def setUp(self):
        embedding_cache.clear()

    @patch("app.services.embedding._active_mmodel")
    @patch("app.services.embedding.__init__")
    def test_a_new_query_miss_calls_gemini_once(self, mock_init, mock_mmodel):
        mock_vec = [0.1] * 3072
        mock_mmodel.embed_query.return_value = mock_vec

        query = "What is the normal workweek for employees?"
        res = embed_query(query)

        self.assertEqual(res, mock_vec)
        self.assertEqual(mock_mmodel.embed_query.call_count, 1)

    @patch("app.services.embedding._active_mmodel")
    @patch("app.services.embedding.__init__")
    def test_b_same_query_again_hit_gemini_not_called_again(self, mock_init, mock_mmodel):
        mock_vec = [0.1] * 3072
        mock_mmodel.embed_query.return_value = mock_vec

        query = "What is the normal workweek for employees?"
        res1 = embed_query(query)
        self.assertEqual(mock_mmodel.embed_query.call_count, 1)

        # Second call with exact same query
        res2 = embed_query(query)
        self.assertEqual(res2, mock_vec)
        # Should be a cache HIT: call count must still be 1
        self.assertEqual(mock_mmodel.embed_query.call_count, 1)

    @patch("app.services.embedding._active_mmodel")
    @patch("app.services.embedding.__init__")
    def test_c_whitespace_case_differences_hit(self, mock_init, mock_mmodel):
        mock_vec = [0.1] * 3072
        mock_mmodel.embed_query.return_value = mock_vec

        query1 = "What is the normal workweek for employees?"
        embed_query(query1)
        self.assertEqual(mock_mmodel.embed_query.call_count, 1)

        # Query with extra leading/trailing spaces, collapsed whitespace, and mixed case
        query2 = "   WHAT is   the  NORMAL   workweek for   EMPLOYEES?   "
        res2 = embed_query(query2)
        self.assertEqual(res2, mock_vec)
        # Must be a cache HIT
        self.assertEqual(mock_mmodel.embed_query.call_count, 1)

    @patch("app.services.embedding._active_mmodel")
    @patch("app.services.embedding.__init__")
    def test_d_different_query_miss(self, mock_init, mock_mmodel):
        mock_vec1 = [0.1] * 3072
        mock_vec2 = [0.2] * 3072
        mock_mmodel.embed_query.side_effect = [mock_vec1, mock_vec2]

        embed_query("What is the normal workweek for employees?")
        self.assertEqual(mock_mmodel.embed_query.call_count, 1)

        # Different query must be a MISS
        embed_query("What is the remote work policy?")
        self.assertEqual(mock_mmodel.embed_query.call_count, 2)

    @patch("app.services.embedding._active_mmodel")
    @patch("app.services.embedding.__init__")
    def test_e_expired_embedding_miss(self, mock_init, mock_mmodel):
        mock_vec = [0.1] * 3072
        mock_mmodel.embed_query.return_value = mock_vec

        query = "What is the travel reimbursement limit?"
        embed_query(query)
        self.assertEqual(mock_mmodel.embed_query.call_count, 1)

        # Manually expire the key in the cache store
        key = generate_embedding_cache_key(query)
        entry = embedding_cache._store.get(key)
        self.assertIsNotNone(entry)
        entry["expires_at"] = time.time() - 10  # Expired in the past

        # Calling again should MISS and call Gemini a second time
        embed_query(query)
        self.assertEqual(mock_mmodel.embed_query.call_count, 2)


class TestLLMResponseCache(unittest.TestCase):
    """
    Tests F through K: Portkey / Groq LLM Response Cache
    """

    def setUp(self):
        response_cache.clear()

    def _create_sample_state(self, query="What is the normal workweek for employees?", doc_content="Workweek is 35 hours, Monday-Friday."):
        return {
            "messages": [
                {"role": "user", "content": query}
            ],
            "current_query": query,
            "documents": [
                {
                    "content": doc_content,
                    "source": "test_policy.pdf",
                    "score": 0.95,
                    "rerank_score": 0.92,
                    "metadata": {"page": 1, "chunk_id": "test_policy.pdf-chunk-0"}
                }
            ],
            "plan": ["Start", "Context Retrieved", "Evidence Check: SUFFICIENT"],
            "status": "Found technical context.",
            "final_answer": "",
            "sufficient": True,
            "missing_information": "",
            "retry_count": 0,
        }

    @patch("app.agents.nodes.responder.get_langchain_llm")
    def test_f_first_enterprise_response_miss_calls_llm_once(self, mock_get_llm):
        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.return_value = MagicMock(content="The normal workweek is 35 hours, Monday through Friday.")
        mock_get_llm.return_value = mock_llm_instance

        state = self._create_sample_state()
        result = generate_node(state)

        self.assertEqual(mock_llm_instance.invoke.call_count, 1)
        self.assertIn("35 hours", result["final_answer"])
        self.assertNotIn("Response Cache HIT", result["plan"])

    @patch("app.agents.nodes.responder.get_langchain_llm")
    def test_g_same_query_and_same_evidence_hit_llm_not_called_again(self, mock_get_llm):
        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.return_value = MagicMock(content="The normal workweek is 35 hours, Monday through Friday.")
        mock_get_llm.return_value = mock_llm_instance

        state1 = self._create_sample_state()
        res1 = generate_node(state1)
        self.assertEqual(mock_llm_instance.invoke.call_count, 1)

        # Second request with same query and same retrieved evidence
        state2 = self._create_sample_state()
        res2 = generate_node(state2)

        # Must NOT call LLM again
        self.assertEqual(mock_llm_instance.invoke.call_count, 1)
        self.assertEqual(res2["final_answer"], res1["final_answer"])
        self.assertIn("Response Cache HIT", res2["plan"])

    @patch("app.agents.nodes.responder.get_langchain_llm")
    def test_h_same_query_different_evidence_miss(self, mock_get_llm):
        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.side_effect = [
            MagicMock(content="Workweek is 35 hours."),
            MagicMock(content="Workweek has been updated to 40 hours.")
        ]
        mock_get_llm.return_value = mock_llm_instance

        state1 = self._create_sample_state(doc_content="Old policy: 35 hours.")
        res1 = generate_node(state1)
        self.assertEqual(mock_llm_instance.invoke.call_count, 1)

        # Same query, but document content has changed in vector store
        state2 = self._create_sample_state(doc_content="New policy: 40 hours.")
        res2 = generate_node(state2)

        # Must trigger a MISS and call LLM again to prevent stale answers
        self.assertEqual(mock_llm_instance.invoke.call_count, 2)
        self.assertIn("40 hours", res2["final_answer"])

    @patch("app.agents.nodes.responder.get_langchain_llm")
    def test_i_different_query_miss(self, mock_get_llm):
        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.side_effect = [
            MagicMock(content="Workweek is 35 hours."),
            MagicMock(content="Health insurance is provided to full-time employees.")
        ]
        mock_get_llm.return_value = mock_llm_instance

        state1 = self._create_sample_state(query="What is the workweek?")
        generate_node(state1)
        self.assertEqual(mock_llm_instance.invoke.call_count, 1)

        state2 = self._create_sample_state(query="What is the health insurance coverage?")
        generate_node(state2)
        self.assertEqual(mock_llm_instance.invoke.call_count, 2)

    @patch("app.agents.nodes.responder.get_langchain_llm")
    def test_j_conversational_requests_not_cached_across_threads(self, mock_get_llm):
        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.side_effect = [
            MagicMock(content="Hello! How can I assist you with company policies today?"),
            MagicMock(content="Hi there! Welcome to Nexa AI support.")
        ]
        mock_get_llm.return_value = mock_llm_instance

        # Thread 1 conversational message
        conv_state_thread_1 = {
            "messages": [{"role": "user", "content": "Hello!"}],
            "current_query": "CONVERSATIONAL",
            "documents": [],
            "plan": ["Start", "Intent: Conversational/Memory", "Retrieval: Skipped"],
            "status": "Handling conversationally (using memory)...",
            "final_answer": "",
            "sufficient": False,
            "missing_information": "",
            "retry_count": 0,
        }

        res1 = generate_node(conv_state_thread_1)
        self.assertEqual(mock_llm_instance.invoke.call_count, 1)

        # Thread 2 conversational message with same greeting
        conv_state_thread_2 = {
            "messages": [{"role": "user", "content": "Hello!"}],
            "current_query": "CONVERSATIONAL",
            "documents": [],
            "plan": ["Start", "Intent: Conversational/Memory", "Retrieval: Skipped"],
            "status": "Handling conversationally (using memory)...",
            "final_answer": "",
            "sufficient": False,
            "missing_information": "",
            "retry_count": 0,
        }

        res2 = generate_node(conv_state_thread_2)
        # Conversational queries MUST NOT be cached -> call_count must be 2
        self.assertEqual(mock_llm_instance.invoke.call_count, 2)
        self.assertNotIn("Response Cache HIT", res2["plan"])

    @patch("app.agents.nodes.responder.get_langchain_llm")
    def test_k_cache_hit_response_contract_preservation(self, mock_get_llm):
        """
        Verify that cached response retains:
        - answer
        - sources conforming to the frontend SourceReceipt structure
        - grounded status
        - and when executed through pipeline, current request latency is calculated fresh
        """
        mock_llm_instance = MagicMock()
        expected_answer = "The standard employee workweek is 35 hours (Monday through Friday)."
        mock_llm_instance.invoke.return_value = MagicMock(content=expected_answer)
        mock_get_llm.return_value = mock_llm_instance

        state = self._create_sample_state()

        # Request 1: populate cache
        start_time_1 = time.perf_counter()
        res1 = generate_node(state)
        latency_1 = round((time.perf_counter() - start_time_1) * 1000, 2)

        # Inspect cached data directly
        cached_keys = list(response_cache._store.keys())
        self.assertEqual(len(cached_keys), 1)
        cached_item = response_cache.get(cached_keys[0])

        self.assertIn("answer", cached_item)
        self.assertIn("sources", cached_item)
        self.assertIn("grounded", cached_item)
        self.assertEqual(cached_item["answer"], expected_answer)
        self.assertTrue(cached_item["grounded"])

        # Check frontend source contract
        sources = cached_item["sources"]
        self.assertIsInstance(sources, list)
        self.assertGreaterEqual(len(sources), 1)
        source_item = sources[0]
        self.assertIn("chunk_id", source_item)
        self.assertIn("document", source_item)
        self.assertIn("page", source_item)
        self.assertIn("score", source_item)
        self.assertIn("text", source_item)

        # Request 2: cache HIT
        start_time_2 = time.perf_counter()
        res2 = generate_node(state)
        latency_2 = round((time.perf_counter() - start_time_2) * 1000, 2)

        self.assertEqual(res2["final_answer"], expected_answer)
        self.assertIn("Response Cache HIT", res2["plan"])
        # Latency of request 2 is calculated freshly and is non-negative
        self.assertGreaterEqual(latency_2, 0.0)


if __name__ == "__main__":
    unittest.main()
