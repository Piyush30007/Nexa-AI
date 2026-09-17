import unittest

from app.agents.nodes.planner import planner_node


class TestPlannerRetry(unittest.TestCase):

    def test_retry_replans_insufficient_evidence(self):
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

        # Planner should perform another search rather than stop.
        self.assertEqual(
            result["status"],
            "Searching for relevant documents..."
        )

        self.assertEqual(result["retry_count"], 1)

        self.assertIn(
            "Intent: Search",
            result["plan"]
        )

        # The retry should produce a search query.
        search_steps = [
            step for step in result["plan"]
            if step.startswith("Search Query:")
        ]

        self.assertGreaterEqual(len(search_steps), 2)

        # The new search should be more specific than the original one.
        self.assertNotEqual(
            search_steps[-1],
            search_steps[-2]
        )


if __name__ == "__main__":
    unittest.main()