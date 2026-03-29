import pytest
from tracker.graph_models import Province, Project, ManifestoPromise

@pytest.mark.django_db
def test_ontology_linkage():
    # Clear any existing data for these nodes to avoid collisions (since unique name)
    for p in Province.nodes.filter(name="Bagmati"):
        p.delete()
    
    # Creates a Province.
    bagmati = Province(name="Bagmati").save()
    
    # Creates a Project and links it to the Province.
    airport = Project(title="Nijgadh Airport", budget=1000000000).save()
    airport.located_in.connect(bagmati)
    
    # Creates a ManifestoPromise and links it to the Project.
    promise = ManifestoPromise(text="We will build an international airport in Nijgadh").save()
    promise.fulfilled_by.connect(airport)
    
    # Verifies all connections.
    # Check Project -> Province
    provinces = airport.located_in.all()
    assert len(provinces) == 1
    assert provinces[0].name == "Bagmati"
    
    # Check ManifestoPromise -> Project
    projects = promise.fulfilled_by.all()
    assert len(projects) == 1
    assert projects[0].title == "Nijgadh Airport"
    
    # Clean up
    promise.delete()
    airport.delete()
    bagmati.delete()
