from app.agents.state import AgentState
from app.config import Settings, settings
from langchain_groq import ChatGroq
from app.gateway import portkey_client, get_langchain_llm , extract_cache_status
from app.services.cache import response_cache, generate_response_cache_key
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
        prompt = f"""You are a friendly and helpful assistant for Nexa AI.
You have access to the conversation history and the latest user message.
Respond politely and concisely to conversational pleasantries, greetings, farewells, gratitude, or basic agent-identity questions.

CONVERSATION HISTORY:
{history_str}

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
            prompt = f"""You are an enterprise AI assistant answering questions based strictly on official company documentation.

TECHNICAL CONTEXT:
{full_context}

CONVERSATION HISTORY:
{history_str}

USER QUESTION:
{user_message}

RULES:
1. Answer the user's question directly, accurately, and concisely based ONLY on the provided TECHNICAL CONTEXT.
2. Do not invent, assume, or extrapolate facts, numbers, dates, or policies not present in the context.
3. If the context contains the answer, state it clearly and factually.
"""
        else:
            logfire.info(f"Generating evidence-bounded response for insufficient evidence (query: {query}) ...")
            missing_info = state.get("missing_information", "").strip() or "Specific policy details for the requested topic."
            prompt = f"""You are an enterprise AI assistant answering questions based on official company documentation.

The evidence retrieved from company documentation is INSUFFICIENT to answer the user's question.

USER QUESTION:
{user_message}

AVAILABLE DOCUMENTATION CONTEXT:
{full_context if full_context.strip() else "No relevant document excerpts found."}

MISSING INFORMATION IDENTIFIED:
{missing_info}

CONVERSATION HISTORY:
{history_str}

CRITICAL RULES:
1. NEVER invent, fabricate, or assume any facts, policies, schedules, hours, rules, or eligibility criteria.
2. Formulate a concise, direct, and helpful response that:
   - Explains what the available documentation DOES establish regarding the topic, if anything relevant is mentioned in the context (e.g. employee policies).
   - Explains what specific requested information is missing from the documentation (e.g. contractor rules, leave accrual details).
   - Explicitly states that the answer cannot be determined from the available documents.
3. Maintain a professional and objective tone. Do not apologize excessively.
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
                "plan": state["plan"] + ["Response Cache HIT"],
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
                "plan": state["plan"],
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