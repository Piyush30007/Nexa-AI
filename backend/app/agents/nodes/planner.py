from app.agents.state import AgentState
import logfire

from app.gateway import get_langchain_llm


llm = get_langchain_llm(feature="planner")


def planner_node(state: AgentState):
    """
    Determines whether the current request is conversational or requires
    document retrieval.

    When the previous retrieval was insufficient, the planner uses the
    sufficiency feedback to generate a better search query.
    """

    history = ""

    for msg in state["messages"][:-1]:
        role = "User" if msg["role"] == "user" else "Assistant"
        history += f"{role}: {msg['content']}\n"

    user_message = (
        state["messages"][-1]["content"]
        if state["messages"]
        else ""
    )

    retry_count = state.get("retry_count", 0)
    missing_information = state.get("missing_information", "")

    # ---------------------------------------------------------
    # Build planner prompt
    # ---------------------------------------------------------

    if retry_count > 0:
        retry_context = f"""
Previous retrieval attempt was insufficient.

Missing information identified:
{missing_information}

This is retrieval attempt #{retry_count + 1}.

Generate a NEW and more precise search query that specifically targets
the missing information.
"""
    else:
        retry_context = """
This is the first retrieval attempt.
Determine whether the user request requires document retrieval.
"""

    prompt = f"""
You are an intelligent planning agent for an enterprise RAG system.

You can use conversation history for context and formulate search queries to retrieve verified information from the enterprise knowledge base.

CONVERSATION HISTORY:
{history}

CURRENT USER QUERY:
{user_message}

{retry_context}

CRITICAL RULES:

1. CLASSIFY AS "CONVERSATIONAL" ONLY IF:
   - The message is a greeting (e.g., "hi", "hello", "hey").
   - The message is a farewell (e.g., "bye", "goodbye").
   - The message is a simple pleasantry or expression of gratitude (e.g., "thanks", "thank you", "okay", "great", "got it").
   - The message is a basic agent-identity question (e.g., "who are you?", "what can you do?", "what is your name?").
   - The user is introducing themselves or making a personal conversational statement without asking for company policies (e.g., "My name is Piyush Singh.", "I work in Engineering.").
   - The user is asking about user-provided personal facts, statements, or continuity from the CONVERSATION HISTORY (e.g., "What is my name?", "What did I just tell you?", "What did I say earlier?", "What were we discussing?", "Can you remind me what I told you?", "Based on what I said earlier..."), AND does NOT request official company policies, benefits, rules, or procedures.

2. ENTERPRISE / DOCUMENT QUESTIONS:
   - Any question seeking factual, procedural, policy, HR, payroll, schedule, security, or enterprise information MUST generate a standalone retrieval search query.
   - Even if the user mentions personal details in the query or conversation history (e.g., "I work in Engineering. What are my working hours?" or "What is the company leave policy for me?"), you MUST generate a standalone retrieval search query for the enterprise policy topic (e.g., "employee working hours policy", "company leave policy").
   - NEVER classify an enterprise, policy, or document question as CONVERSATIONAL.
   - When in doubt, ALWAYS prefer retrieval.

3. REPEATED QUESTIONS (STRICT):
   - If the user asks an enterprise or policy question that was already asked or answered in the CONVERSATION HISTORY, NEVER output CONVERSATIONAL.
   - Even if the answer is clearly present in the conversation history, you MUST generate a standalone search query to retrieve fresh evidence.
   - Conversation history provides context, but enterprise retrieval is the sole source of truth.

4. CONTEXTUAL FOLLOW-UPS:
   - If the user asks a follow-up question that depends on previous conversation history (e.g., "What about contractors?", "How about interns?", "Who approves that?"), resolve any references or pronouns using the conversation history and generate a complete, self-contained standalone search query (e.g., "employee workweek policy for contractors").
   - Do NOT answer follow-ups from memory. Route them through retrieval.

5. RETRIEVAL RETRIES:
   - If this is a retry attempt (retry_count > 0), generate a DIFFERENT, more specific search query directly targeting the identified missing information.
   - Do NOT output CONVERSATIONAL during a retry attempt.

6. OUTPUT FORMAT:
   - Do not answer the user's question.
   - Do not provide explanations, preamble, or punctuation.
   - Output EXACTLY ONE of:

CONVERSATIONAL

OR

<standalone search query>
"""

    # ---------------------------------------------------------
    # LLM decision
    # ---------------------------------------------------------

    with logfire.span("Planner Decision"):

        try:
            llm = get_langchain_llm(feature="planner")
            decision = llm.invoke(prompt).content.strip()
            decision = decision.strip("\"' \n\r")

        except Exception as e:
            logfire.error(f"Planner failed: {e}")
            raise

    logfire.info(
        f"Planner Decision: {decision} | Retry Count: {retry_count}"
    )

    # ---------------------------------------------------------
    # Conversational route
    # ---------------------------------------------------------

    if decision.lower() == "conversational":

        return {
            "current_query": "CONVERSATIONAL",
            "status": "Handling conversationally (using memory)...",
            "plan": state.get("plan", []) + [
                "Intent: Conversational/Memory",
                "Retrieval: Skipped",
            ],
        }

    # ---------------------------------------------------------
    # Retrieval route
    # ---------------------------------------------------------

    return {
        "current_query": decision,
        "status": "Searching for relevant documents...",
        "plan": state.get("plan", []) + [
            "Intent: Search",
            f"Search Query: {decision}",
        ],
        "retry_count": retry_count,
    }

    """
       User
                    │
              NeMo Guardrails
                    │
                 Planner
                /       \
               /         \
       Conversational   Enterprise
             │              │
       Conversation      Qdrant
         Memory             │
             │           FlashRank
             │              │
             │         Sufficiency
             │           /      \
             │      sufficient  insufficient
             │          │           │
             │       Response     Retry
             │                      │
             │                   Planner
             │
             └──────────────┬──────────────┘
                            │
                         Response
    """