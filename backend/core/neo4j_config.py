import os
from neomodel import get_config

config = get_config()

# Construct Neo4j URL from individual env vars or single URL
neo4j_url = os.getenv("NEO4J_URL", "").strip()
if not neo4j_url:
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687").strip()
    user = os.getenv("NEO4J_USERNAME", os.getenv("NEO4J_USER", "neo4j")).strip()
    password = os.getenv("NEO4J_PASSWORD", "password").strip()

    # If URI starts with neo4j+s:// or bolt://, inject auth credentials
    if "://" in uri:
        scheme, host = uri.split("://", 1)
        neo4j_url = f"{scheme}://{user}:{password}@{host}"
    else:
        neo4j_url = f"bolt://{user}:{password}@{uri}"

config.database_url = neo4j_url
