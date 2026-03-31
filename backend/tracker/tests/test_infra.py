from neomodel import db
import pytest

@pytest.mark.django_db
def test_neo4j_connection():
    results, meta = db.cypher_query("RETURN 1 as check")
    assert results[0][0] == 1
