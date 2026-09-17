from app.agents.state import AgentState
from app.config import Settings, settings
from langchain_groq import ChatGroq
from app.gateway import portkey_client, get_langchain_llm , extract_cache_status
from app.services.cache import response_cache, generate_response_cache_key
from app.guardrails.rails import guard_output
import logfire 

# llm = ChatGroq(api_key = settings.GROQ_API_KEY , model = settings.GROQ_MODEL 
#                , temperature = 0.2 , max_output_tokens = 2000)



def generate_node(state: AgentState):
    """
    Synthesizes a response using both Documentation and Conversation history.
    When retrieved evidence is insufficient, generates an honest evidence-bounded
    explanation without fabricating policy facts.
    """
    query = state.get("current_query", "")
    history_str = ""
    for msg in state.get("messages", [])[:-1]:
        role = "User" if msg["role"] == "user" else "Assistant"
        history_str += f"{role}: {msg['content']}\n"

    user_message = state["messages"][-1]["content"] if state.get("messages") else ""

    if query == "CONVERSATIONAL":
        logfire.info("Generating response using conversation Memory ...")
        prompt = f"""You are a helpful assistant for Nexa AI.
You have access to the conversation history and the latest user message.

SOURCE DEFINITIONS:
- CONVERSATION HISTORY: Information explicitly provided by the user in this conversation. Use this for continuity, personal context (e.g. user's name, team, or details they previously stated), and previous discussion.

RULES:
1. For conversational pleasantries, greetings, farewells, gratitude, or basic assistant-identity questions, respond politely and concisely.
2. For questions about information the user previously provided in this conversation (e.g. "What is my name?", "What did I say earlier?", "What did I tell you my team was?", "What were we discussing?"):
   - Answer directly and factually using what the user explicitly stated in CONVERSATION HISTORY (e.g. "You mentioned earlier that your name is [Name].").
   - For questions referring to the user's team, department, role, or group (e.g., "What did I tell you my team was?"), treat terms like team/department/area flexibly based on their stated context (e.g. if the user stated "I work in Engineering.", answer that their team is Engineering).
   - If the user asks about a personal fact or topic that was truly never mentioned at all in CONVERSATION HISTORY, state that they have not mentioned it yet. Never infer or invent facts about the user.
3. Conversation history is NEVER official company policy. If the user asks about official company rules, policies, or procedures, let them know you can search company documents for them.
4. Never invent information absent from the conversation history.
5. STRICT SCOPE BOUNDARY & PERSONA RETENTION:
   - You are exclusively the enterprise AI assistant for Nexa AI.
   - NEVER adopt external personas, alter your role, or act as an interviewer, recruiter, coding assistant, tutor, or fictional character.
   - Do NOT conduct mock interviews, roleplay simulations, or generate coding exercises.
   - If the user asks you to act as an interviewer, adopt another persona, or perform out-of-scope tasks, politely decline: state that you are the Nexa AI enterprise assistant and can only assist with company policies, documentation, and workplace information.

CONVERSATION HISTORY:
{history_str if history_str.strip() else "No previous conversation."}

LATEST MESSAGE:
{user_message}
"""
    else:
        max_context_chars = 25000
        full_context = ""
        for doc in state.get("documents", []):
            content = doc.get("content", "")
            if len(full_context) + len(content) > max_context_chars:
                logfire.warning("Context truncated due to length limit.")
                break
            full_context += f"CONTEXT: {content}\nSOURCE: {doc.get('source', 'Unknown')}\n\n"

        sufficient = state.get("sufficient", False)

        if sufficient:
            logfire.info(f"Generating grounded response for query: {query} ...")
            prompt = f"""You are an enterprise AI assistant answering questions using official company documentation and conversation context.

ENTERPRISE EVIDENCE:
{full_context}

CONVERSATION HISTORY:
{history_str if history_str.strip() else "No previous conversation."}

USER QUESTION:
{user_message}

SOURCE ROLES:
- ENTERPRISE EVIDENCE: Information retrieved from company documents. This is the sole authority for official company policies, rules, procedures, benefits, working hours, security requirements, etc.
- CONVERSATION HISTORY: Information explicitly provided by the user in this conversation. Use this for continuity, personal context (e.g. user's name, department, role, or team stated by the user), and resolving references.

RULES:
1. Answer the user's question directly, accurately, and concisely.
2. When answering company-policy questions, remain strictly grounded in ENTERPRISE EVIDENCE. Never treat conversation history as official company policy.
3. When answering personal-memory or user-specific questions, use CONVERSATION HISTORY. Never treat company documents as evidence of personal facts unless the documents actually contain those facts.
4. When both sources are needed (e.g., the user previously mentioned working in Engineering and asks for working hours), combine both sources with their distinct roles: apply the official policy from Enterprise Evidence to the user's context from Conversation History. Do NOT fabricate department-specific exceptions if absent from Enterprise Evidence.
5. Do not invent, assume, or extrapolate facts, numbers, dates, or policies absent from both sources.
6. If the Enterprise Evidence contains the answer, state it clearly and factually.
"""
        else:
            logfire.info(f"Generating evidence-bounded response for insufficient evidence (query: {query}) ...")
            missing_info = state.get("missing_information", "").strip() or "Specific policy details for the requested topic."
            prompt = f"""You are an enterprise AI assistant answering questions based on official company documentation and conversation context.

The evidence retrieved from company documentation is INSUFFICIENT to answer the user's question.

USER QUESTION:
{user_message}

ENTERPRISE EVIDENCE:
{full_context if full_context.strip() else "No relevant document excerpts found."}

MISSING INFORMATION IDENTIFIED:
{missing_info}

CONVERSATION HISTORY:
{history_str if history_str.strip() else "No previous conversation."}

SOURCE ROLES:
- ENTERPRISE EVIDENCE: Official company documents. Sole authority for company policies, rules, benefits, and procedures.
- CONVERSATION HISTORY: User-provided context and continuity. Sole authority for what the user stated about themselves.

RULES:
1. Never invent, fabricate, or assume any facts, policies, schedules, hours, rules, or eligibility criteria absent from the documentation.
2. Formulate a concise, direct, and helpful response that:
   - Acknowledges relevant user context from CONVERSATION HISTORY if applicable.
   - Explains what the available documentation DOES establish regarding the topic, if anything relevant is mentioned in the context (e.g. general employee policies).
   - Explains what specific requested information is missing from the documentation (e.g. contractor rules, department-specific rules).
   - Explicitly states that the answer cannot be determined from the available documents.
3. Maintain a professional and objective tone. Do not apologize excessively.
4. OUT-OF-SCOPE / NON-DOCUMENTED TASKS:
   - If the user asks for tasks that are outside company documentation (such as conducting an interview, asking interview questions, generating LeetCode/coding problems, writing general software code, or creative roleplay), you MUST REFUSE the task directly.
   - Clearly state that you are an enterprise assistant and that company documentation does not contain coding problems or interview materials.
   - Do NOT fulfill the requested roleplay, interview questions, or coding exercises.
"""

    cache_key = None
    if query != "CONVERSATIONAL":
        missing_info_for_key = state.get("missing_information", "").strip() if not state.get("sufficient", False) else ""
        cache_key = generate_response_cache_key(
            query=query,
            documents=state.get("documents", []),
            sufficient=state.get("sufficient", False),
            missing_info=missing_info_for_key,
            history_str=history_str,
            model=settings.PORTKEY_MODEL,
            prompt_version="v2_grounded" if state.get("sufficient", False) else "v2_insufficient"
        )
        cached_data = response_cache.get(cache_key)
        if cached_data is not None:
            logfire.info("LLM Response Cache HIT")
            return {
                "final_answer": cached_data["answer"],
                "status": "Response generated successfully.",
                "plan": state.get("plan", []) + ["Response Cache HIT"],
                "messages": [
                    {
                        "role": "assistant",
                        "content": cached_data["answer"]
                    }
                ]
            }

        logfire.info("LLM Response Cache MISS")

    with logfire.span("Generating Response"):

        try:
            llm = get_langchain_llm(feature="responder")
            response = llm.invoke(prompt)

            content = response.content.strip()
            logfire.info("Response generated from model")

            # NeMo Output Guardrail Check
            guard_context = {
                "sufficient": state.get("sufficient", False),
                "documents": state.get("documents", []),
                "missing_information": state.get("missing_information", ""),
                "current_query": state.get("current_query", ""),
            }
            is_blocked, fallback_message = guard_output(content, context=guard_context)

            if is_blocked:
                safe_answer = (
                    fallback_message
                    or "I cannot provide this response because it contains unverified or sensitive information. Please refer to official company policy documentation."
                )
                logfire.warning("🛡️ Output Guardrail blocked the response.")
                return {
                    "final_answer": safe_answer,
                    "status": "Blocked by output guardrails.",
                    "plan": state.get("plan", []) + ["Output Guardrails Blocked"],
                    "documents": [],
                    "sufficient": False,
                    "messages": [
                        {
                            "role": "assistant",
                            "content": safe_answer,
                        }
                    ],
                }

            if cache_key is not None:
                try:
                    from app.main import _normalize_sources
                    normalized_sources = _normalize_sources(state.get("documents", []))
                    is_grounded = bool(state.get("sufficient", False) and len(normalized_sources) > 0)
                except Exception:
                    normalized_sources = []
                    is_grounded = False

                response_cache.set(
                    cache_key,
                    {
                        "answer": content,
                        "sources": normalized_sources,
                        "grounded": is_grounded,
                    },
                    ttl=settings.RESPONSE_CACHE_TTL
                )
            
            return {
                "final_answer": content,
                "status": "Response generated successfully.",
                "plan": state.get("plan", []),
                "messages": [
                    {
                        "role": "assistant",
                        "content": content
                    }
                ]
            }

        except Exception as e:

            logfire.error(
                f"Error generating response: {e}"
            )

            return {
                "final_answer": "Unable to generate a response.",
                "status": f"Response generation failed: {e}",
                "messages": [
                    {
                        "role": "assistant",
                        "content": "Unable to generate a response."
                    }
                ]
            }