from app.agents.state import AgentState
from app.config import Settings, settings
from langchain_groq import ChatGroq
import logfire 

# llm = ChatGroq(api_key = settings.GROQ_API_KEY , model = settings.GROQ_MODEL 
#                , temperature = 0.2 , max_output_tokens = 2000)

from app.gateway import portkey_client, get_langchain_llm , extract_cache_status

def generate_node(state : AgentState):
    """
    
    Synthesizes a response using both 
    Documentation and Conversation history.
    Args:
        state (AgentState): _description_
    """
    query = state["current_query"]
    history_str = ""
    for msg in state["messages"][:-1]:
            role  = "User" if msg["role"] == "user" else "Assistant"
            history_str += f"{role}: {msg['content']}\n"
            
    user_message = state["messages"][-1]["content"]  if state["messages"] else ""
    if query == "CONVERSATIONAL":
        logfire.info("Generating response using conversation Memory ...")
        prompt = f"""
        You are a friendly and helpful assistant. You have access to the entire conversation history and the current user query. Use this information to generate a response that is relevant, informative, and engaging.   
        
        CONVERSATION HISTORY: {history_str}
        LATEST MESSAGE: {user_message}
        """
        
    else:
        logfire.info(f"Generating response using search results for query: {query} ...")
        max_context_chars = 25000
        full_context = ""
        for doc in state["documents"]:
            if len(full_context) + len(doc) > max_context_chars:
                logfire.warning("Context truncated due to length limit.")
                break
            full_context += doc + "\n"
            
            
        prompt = f"""
        You are a friendly and helpful assistant. You have access to the entire conversation history, the current user query, and relevant search results. Use this information to generate a response that is relevant, informative, and engaging.
        TECHNICAL CONTEXT: {full_context}
        CONVERSATION HISTORY: {history_str}
        
        USER QUESTION : {user_message}
        """
        
    with logfire.span("Generating Response"):
        
        try :
            response  = portkey_client.chat.completions.create(
             message = [{"role" : "user" , "content" : prompt}] ,
             temperature = 0.1,  
            )
            content = response.choices[0].message.content
            cache_status = extract_cache_status(response)
            is_cached_hit = cache_status == "HIT"
            if is_cached_hit:
                logfire.info("Response generated from cache.")
                plan_update = state["plant"] + ["Cache : HIT"]
                status = "Response generated from cache."
            else :
                logfire.info("Response generated from model.")
                plan_update = state["plan"] 
                status = "Response generated successfully." 
            return {
                "final_answer" : content,
                "status" : status,
                "plan" : plan_update,
                "messages" : state["messages"] + [{"role" : "assistant" , "content" : content}]
                
            }
        except Exception as e:
            logfire.error(f"Error generating response: {e}")
           
        
        
