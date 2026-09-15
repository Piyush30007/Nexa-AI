from typing import List , TypedDict , Literal,Annotated
import operator 

class AgentState(TypedDict):
    """
    Using Annotated with operator add ensures that messages 
    are always appended to the list, rather than replacing it.
    """
    messages : Annotated[List[dict], operator.add] 
    """
    The list of messages in the agent's conversation history.
    Each message is a dictionary with keys like 'role' and 'content'.
    """
    current_query : str
    documents : List[str]
    plan : List[str]
    status : str
    final_answer : str
    
    