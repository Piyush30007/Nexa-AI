from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.agents.state import AgentState
from app.agents.nodes.planner import planner_node
from app.agents.nodes.retriever import retrieve_node
from app.agents.nodes.sufficiency import sufficiency_node
from app.agents.nodes.responder import generate_node


workflow = StateGraph(AgentState)

# Nodes
workflow.add_node("planner", planner_node)
workflow.add_node("retriever", retrieve_node)
workflow.add_node("sufficiency", sufficiency_node)
workflow.add_node("responder", generate_node)


# ---------------------------------------------------------
# Planner routing
# ---------------------------------------------------------

def route_planner(state: AgentState):
    """
    Decide whether the request needs retrieval or can be
    answered directly from conversation memory.
    """

    if state["current_query"] == "CONVERSATIONAL":
        return "responder"

    return "retriever"


# ---------------------------------------------------------
# Sufficiency routing
# ---------------------------------------------------------

def route_sufficiency(state: AgentState):
    """
    Decide whether retrieved evidence is sufficient.

    If sufficient:
        → responder

    If insufficient:
        → planner for another retrieval attempt

    Retry limit prevents an infinite reasoning loop.
    """

    if state["sufficient"]:
        return "responder"

    if state["retry_count"] >= 2:
        return "responder"

    return "planner"


# ---------------------------------------------------------
# Graph structure
# ---------------------------------------------------------

workflow.set_entry_point("planner")


workflow.add_conditional_edges(
    "planner",
    route_planner,
    {
        "retriever": "retriever",
        "responder": "responder",
    },
)


workflow.add_edge("retriever", "sufficiency")


workflow.add_conditional_edges(
    "sufficiency",
    route_sufficiency,
    {
        "responder": "responder",
        "planner": "planner",
    },
)


workflow.add_edge("responder", END)


# ---------------------------------------------------------
# Memory / checkpointing
# ---------------------------------------------------------

checkpointer = MemorySaver()

rag_agent = workflow.compile(
    checkpointer=checkpointer
)