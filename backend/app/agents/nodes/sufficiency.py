import logfire

from app.agents.state import AgentState
from app.gateway import get_langchain_llm





def sufficiency_node(state: AgentState):
    """
    Checks whether the retrieved documents contain enough evidence
    to answer the user's question.

    If evidence is insufficient, the node identifies what information
    is missing so the planner can perform another retrieval attempt.
    """

    query = state["current_query"]
    documents = state["documents"]

    # ---------------------------------------------------------
    # Build evidence context
    # ---------------------------------------------------------

    max_context_chars = 12000
    context = ""

    for doc in documents:
        content = doc.get("content", "")
        source = doc.get("source", "Unknown")

        if len(context) + len(content) > max_context_chars:
            break

        context += (
            f"CONTENT: {content}\n"
            f"SOURCE: {source}\n\n"
        )

    # ---------------------------------------------------------
    # Sufficiency prompt
    # ---------------------------------------------------------

    prompt = f"""
You are an evidence sufficiency checker for an enterprise RAG system.

Your job is to determine whether the retrieved documentation contains
enough reliable information to answer the user's question.

USER QUESTION:
{query}

RETRIEVED DOCUMENTATION:
{context}

Rules:

1. Return "SUFFICIENT" if the documentation contains enough information
   to directly answer the question.

2. Return "INSUFFICIENT" if the documentation is missing important
   information needed to answer the question.

3. Do not use outside knowledge.

4. If the evidence is insufficient, briefly explain what information
   is missing.

Output EXACTLY in this format:

DECISION: SUFFICIENT
MISSING: None

OR

DECISION: INSUFFICIENT
MISSING: <brief description of missing information>
"""

    # ---------------------------------------------------------
    # Run evidence checker
    # ---------------------------------------------------------
    llm = get_langchain_llm(feature="sufficiency")
    with logfire.span("Evidence Sufficiency Check"):

        try:
            response = llm.invoke(prompt)
            result = response.content.strip()

            logfire.info(
                f"Sufficiency result: {result}"
            )

            # -------------------------------------------------
            # Parse LLM response
            # -------------------------------------------------

            lines = result.splitlines()

            # Fail closed
            decision = "INSUFFICIENT"

            missing_information = (
                "The retrieved documentation is insufficient."
            )

            for line in lines:

                if line.upper().startswith("DECISION:"):

                    value = (
                        line.split(":", 1)[1]
                        .strip()
                        .upper()
                    )

                    if value == "SUFFICIENT":
                        decision = "SUFFICIENT"

                elif line.upper().startswith("MISSING:"):

                    missing_information = (
                        line.split(":", 1)[1]
                        .strip()
                    )

            sufficient = decision == "SUFFICIENT"

            # -------------------------------------------------
            # Retry counter
            # -------------------------------------------------

            retry_count = state.get("retry_count", 0)  

            # Only count an actual insufficient retrieval
            # as a retry.
            if not sufficient:
                retry_count += 1

            # -------------------------------------------------
            # Return updated state
            # -------------------------------------------------

            return {
                "sufficient": sufficient,

                "missing_information": (
                    ""
                    if sufficient
                    else missing_information
                ),

                "retry_count": retry_count,

                "status": (
                    "Evidence is sufficient."
                    if sufficient
                    else "Evidence is insufficient. Re-planning required."
                ),

                "plan": state["plan"] + [
                    (
                        "Evidence Check: SUFFICIENT"
                        if sufficient
                        else "Evidence Check: INSUFFICIENT"
                    )
                ],
            }

        # -----------------------------------------------------
        # Failure handling
        # -----------------------------------------------------

        except Exception as e:

            logfire.error(
                f"Sufficiency check failed: {e}"
            )

            # Do not consume a retrieval retry when the
            # evidence-checking LLM itself fails.
            return {
                "sufficient": False,

                "missing_information": (
                    "Evidence verification failed. "
                    "Additional retrieval is required."
                ),

                "retry_count": state.get("retry_count", 0) + 1,

                "status": "Evidence verification failed.",

                "plan": state["plan"] + [
                    "Evidence Check: FAILED"
                ],
            }