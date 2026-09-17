from app.agents.graph import rag_agent


initial_state = {
    "messages": [
        {
            "role": "user",
            "content": "How to get travel policy?"
        }
    ],
    "current_query": "",
    "documents": [],
    "plan": [],
    "status": "",
    "final_answer": "",
    "sufficient": False,
    "missing_information": "",
    "retry_count": 0,
}


config = {
    "configurable": {
        "thread_id": "test-thread-1"
    }
}


result = rag_agent.invoke(
    initial_state,
    config=config
)


print("\n========== FINAL ANSWER ==========\n")
print(result["final_answer"])

print("\n========== STATUS ==========\n")
print(result["status"])

print("\n========== CURRENT QUERY ==========\n")
print(result["current_query"])

print("\n========== RETRY COUNT ==========\n")
print(result["retry_count"])

print("\n========== SUFFICIENT ==========\n")
print(result["sufficient"])

print("\n========== PLAN ==========\n")
for step in result["plan"]:
    print("-", step)

print("\n========== DOCUMENTS ==========\n")
for doc in result["documents"]:
    print({
        "source": doc.get("source"),
        "score": doc.get("score"),
        "rerank_score": doc.get("rerank_score"),
    })