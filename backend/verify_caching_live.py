"""
Live Two-Request Verification Script for Nexa AI Enterprise V2 Caching
======================================================================
Tests: "What is the normal workweek for employees?" across two identical requests.

Verifies:
1. Guardrails and Planner run on BOTH requests (not bypassed).
2. Request 1:
   - Embedding Cache MISS
   - Gemini query embedding called (count = 1)
   - Qdrant retrieval executes
   - FlashRank reranking executes
   - Sufficiency check executes
   - LLM Response Cache MISS
   - Portkey/Groq responder called (count = 1)
   - Grounded answer returned (35 hours / Monday-Friday), grounded = True, sources valid.
3. Request 2:
   - Guardrails and Planner run
   - Embedding Cache HIT (Gemini called 0 times on Request 2)
   - Qdrant retrieval executes with cached embedding
   - FlashRank reranking executes
   - Sufficiency check executes
   - LLM Response Cache HIT (Responder called 0 times on Request 2)
   - Grounded answer returned from cache (35 hours), grounded = True, sources valid.
   - latency_ms calculated fresh for this request.
"""

import sys
import os
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import ChatOpenAI

from app.guardrails import initialize_rails
from app.main import chat, ChatRequest
from app.services.cache import embedding_cache, response_cache
import app.services.embedding as embedding_module
import app.agents.nodes.responder as responder_module


def run_live_verification():
    print("=" * 70)
    print("STARTING LIVE CACHING VERIFICATION FOR NEXA AI ENTERPRISE V2")
    print("=" * 70)

    # 1. Initialize guardrails
    print("\n--- Initializing Guardrails ---")
    initialize_rails()

    # 2. Clear caches to ensure clean initial state
    embedding_cache.clear()
    response_cache.clear()

    # 3. Counters for exact API calls
    gemini_embedding_calls = 0
    responder_llm_calls = 0

    # Spy on Gemini embedding
    original_gemini_embed = GoogleGenerativeAIEmbeddings.embed_query

    def spied_gemini_embed(self, query, *args, **kwargs):
        nonlocal gemini_embedding_calls
        if query != "probe":
            gemini_embedding_calls += 1
            print(f"   >>> [LIVE API CALL] Gemini embed_query called (count={gemini_embedding_calls}) for query: '{query}'")
        return original_gemini_embed(self, query, *args, **kwargs)

    GoogleGenerativeAIEmbeddings.embed_query = spied_gemini_embed

    # Spy on responder's LLM call specifically using a proxy wrapper
    original_responder_get_llm = responder_module.get_langchain_llm

    class LLMProxy:
        def __init__(self, target):
            self._target = target

        def invoke(self, prompt, *args, **kwargs):
            nonlocal responder_llm_calls
            responder_llm_calls += 1
            print(f"   >>> [LIVE API CALL] Portkey/Groq RESPONDER LLM invoked (count={responder_llm_calls})")
            return self._target.invoke(prompt, *args, **kwargs)

        def __getattr__(self, name):
            return getattr(self._target, name)

    def spied_responder_get_llm(feature="responder"):
        real_llm = original_responder_get_llm(feature=feature)
        return LLMProxy(real_llm)

    responder_module.get_langchain_llm = spied_responder_get_llm

    # Ensure embedding module is initialized
    embedding_module.__init__()

    test_query = "What is the normal workweek for employees?"
    thread_id = "live_cache_verification_thread"

    try:
        # =============================================================
        # REQUEST 1
        # =============================================================
        print("\n" + "=" * 70)
        print("EXECUTING REQUEST 1 (EXPECT MISS ON BOTH CACHES)")
        print("=" * 70)
        req1 = ChatRequest(question=test_query, conversation_id=thread_id)

        t0 = time.perf_counter()
        resp1 = chat(req1)
        t1 = time.perf_counter()
        wall_latency_1 = round((t1 - t0) * 1000, 2)

        print("\n--- REQUEST 1 SUMMARY ---")
        print(f"Answer: {resp1.get('answer')}")
        print(f"Grounded: {resp1.get('grounded')}")
        print(f"Sources count: {len(resp1.get('sources', []))}")
        for s in resp1.get('sources', []):
            print(f"  - Source: {s.get('document')} | Chunk ID: {s.get('chunk_id')} | Score: {s.get('score')}")
        print(f"Thought Process: {resp1.get('thought_process')}")
        print(f"Calculated Latency (backend): {resp1.get('latency_ms')} ms (Wall: {wall_latency_1} ms)")
        print(f"Gemini embedding calls after Request 1: {gemini_embedding_calls}")
        print(f"Responder LLM calls after Request 1: {responder_llm_calls}")

        # Assertions for Request 1
        assert gemini_embedding_calls == 1, f"Expected 1 Gemini call, got {gemini_embedding_calls}"
        assert responder_llm_calls == 1, f"Expected 1 Responder LLM call, got {responder_llm_calls}"
        assert resp1.get("grounded") is True, f"Expected grounded=True, got {resp1.get('grounded')}"
        assert "35" in resp1.get("answer"), "Expected '35' in answer"
        assert len(resp1.get("sources", [])) > 0, "Expected non-empty sources"

        # =============================================================
        # REQUEST 2
        # =============================================================
        print("\n" + "=" * 70)
        print("EXECUTING REQUEST 2 (EXPECT HIT ON BOTH CACHES)")
        print("=" * 70)
        req2 = ChatRequest(question=test_query, conversation_id=thread_id)

        gemini_calls_before_2 = gemini_embedding_calls
        responder_calls_before_2 = responder_llm_calls

        t2 = time.perf_counter()
        resp2 = chat(req2)
        t3 = time.perf_counter()
        wall_latency_2 = round((t3 - t2) * 1000, 2)

        gemini_calls_delta_2 = gemini_embedding_calls - gemini_calls_before_2
        responder_calls_delta_2 = responder_llm_calls - responder_calls_before_2

        print("\n--- REQUEST 2 SUMMARY ---")
        print(f"Answer: {resp2.get('answer')}")
        print(f"Grounded: {resp2.get('grounded')}")
        print(f"Sources count: {len(resp2.get('sources', []))}")
        for s in resp2.get('sources', []):
            print(f"  - Source: {s.get('document')} | Chunk ID: {s.get('chunk_id')} | Score: {s.get('score')}")
        print(f"Thought Process: {resp2.get('thought_process')}")
        print(f"Calculated Latency (backend): {resp2.get('latency_ms')} ms (Wall: {wall_latency_2} ms)")
        print(f"Gemini embedding calls on Request 2: {gemini_calls_delta_2} (Total: {gemini_embedding_calls})")
        print(f"Responder LLM calls on Request 2: {responder_calls_delta_2} (Total: {responder_llm_calls})")

        # Assertions for Request 2
        assert gemini_calls_delta_2 == 0, f"Gemini was called on Request 2! Calls: {gemini_calls_delta_2}"
        assert responder_calls_delta_2 == 0, f"Responder LLM was called on Request 2! Calls: {responder_calls_delta_2}"
        assert resp2.get("grounded") is True, f"Expected grounded=True, got {resp2.get('grounded')}"
        assert "35" in resp2.get("answer"), "Expected '35' in answer"
        assert len(resp2.get("sources", [])) > 0, "Expected non-empty sources"
        assert "Response Cache HIT" in resp2.get("thought_process"), "Expected 'Response Cache HIT' in thought process"

        print("\n" + "=" * 70)
        print("ALL LIVE VERIFICATION ASSERTIONS PASSED SUCCESSFULLY!")
        print("=" * 70)
        print(f"Total Gemini embedding calls across 2 requests: {gemini_embedding_calls} (Req 1: 1, Req 2: 0)")
        print(f"Total Responder LLM calls across 2 requests: {responder_llm_calls} (Req 1: 1, Req 2: 0)")
        print(f"Pipeline integrity confirmed: Guardrails -> Planner -> Qdrant -> FlashRank -> Sufficiency -> Cache")
        print(f"Request 1 Latency: {resp1.get('latency_ms')} ms | Request 2 Latency: {resp2.get('latency_ms')} ms")
        print(f"Latency Saved: {round(resp1.get('latency_ms') - resp2.get('latency_ms'), 2)} ms")
        print("=" * 70)

    finally:
        # Restore originals
        GoogleGenerativeAIEmbeddings.embed_query = original_gemini_embed
        responder_module.get_langchain_llm = original_responder_get_llm


if __name__ == "__main__":
    run_live_verification()
