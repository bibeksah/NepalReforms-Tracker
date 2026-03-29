from langgraph.graph import StateGraph, END
from .ingestion import TrackerState, ingest_lal_kitab

def create_workflow():
    """Initializes the tracker workflow graph."""
    workflow = StateGraph(TrackerState)
    
    # Add nodes
    workflow.add_node("ingest", ingest_lal_kitab)
    
    # Define edges
    workflow.set_entry_point("ingest")
    workflow.add_edge("ingest", END)
    
    return workflow.compile()
