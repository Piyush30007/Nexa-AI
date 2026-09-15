from app.agents.state import AgentState
from app.config import Settings, settings
from langchain_groq import ChatGroq
import logfire 
from app.gateway import portkey_client, get_langchain_llm , extract_cache_status

# llm = ChatGroq(api_key = settings.GROQ_API_KEY , model = settings.GROQ_MODEL 
#                , temperature = 0.2 , max_output_tokens = 2000)

llm = get_langchain_llm(feature="planner")

def planner_node(state : AgentState):
    """
    The planner node determines if a search is need baes on the entire conversation history and the current query.
    It returns a plan for the next steps, which may include searching for relevant documents or directly answering the query.
    

    
    """
    history = ""
    for msg in state["messages"][:-1]:
        role  = "User" if msg["role"] == "user" else "Assistant"
        history += f"{role}: {msg['content']}\n"
        
    user_message = state["messages"][-1]["content"]  if state["messages"] else ""
    
    prompt = f"""
You are an intelligent agent that can answer questions based on a conversation history and a current user query.
Conversation History:
{history}
Current User Query:
{user_message}
Task :
1 . If The latest message is a greeting (hi , hello , hey) or a farewell (bye , goodbye) , that can be answered using ONLY the conversation history above(e.g "What is my name ?") and the current user query.
2 . If it is question that requires external information  or if the conversation history does not provide enough context to answer the query, output a redefined search query .
Output Only 'Conversattional' or the search query .
"""
    with logfire.span("Planner Descision"):
        
        decision = llm.invoke(prompt).content.strip()
    logfire.info(f"Planner Decision: {decision}")
    
    if decision.lower() == "conversational":
        return {
            "current_query" : "CONVERSATIONAL",
            "status" : "Handling conversationally (using memory)...",
            "plan" : ["Intent : Conversational/Memory" , "Retrieval : Skipped"]
            
            
        }
        
    return {
        "current_query" : decision,
        "status" : "Searching for relevant documents...",
        "plan" : ["Intent : Search" , f"Search Query : {decision}"] 
    }

