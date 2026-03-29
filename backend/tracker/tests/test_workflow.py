import pytest
from ..agents.workflow import create_workflow

def test_workflow_ingestion():
    """Test that the workflow correctly ingests mock data."""
    workflow = create_workflow()
    
    # Initial state
    initial_state = {
        "raw_data": [],
        "processed_projects": [],
        "matches": []
    }
    
    # Invoke workflow
    final_state = workflow.invoke(initial_state)
    
    # Assertions
    assert "raw_data" in final_state
    assert len(final_state["raw_data"]) == 1
    assert final_state["raw_data"][0]["title"] == "Bagmati Highway"
    assert final_state["raw_data"][0]["budget"] == 5000000
