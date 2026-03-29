from typing import TypedDict, List, Dict, Any

class TrackerState(TypedDict):
    raw_data: List[Dict[str, Any]]
    processed_projects: List[Dict[str, Any]]
    matches: List[Dict[str, Any]]

def ingest_lal_kitab(state: TrackerState) -> Dict[str, Any]:
    """Mock ingestion node for Lal Kitab data."""
    return {"raw_data": [{"title": "Bagmati Highway", "budget": 5000000}]}
