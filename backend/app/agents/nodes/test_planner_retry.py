from app.agents.nodes.planner import planner_node


state = {
    "messages": [
        {
            "role": "user",
            "content": "What does the company policy say about submitting requests?"
        }
    ],
    "current_query": "company policy submitting requests",
    "documents": [],
    "plan": [
        "Intent: Search",
        "Search Query: company policy submitting requests",
        "Evidence Check: INSUFFICIENT"
    ],
    "status": "Evidence is insufficient. Re-planning required.",
    "final_answer": "",
    "sufficient": False,
    "missing_information": (
        "Information about the company policy and procedures "
        "for submitting requests."
    ),
    "retry_count": 1,
}


result = planner_node(state)

print(result)