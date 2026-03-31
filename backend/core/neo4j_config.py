from neomodel import get_config
import os
config = get_config()
config.database_url = os.getenv('NEO4J_URL', 'bolt://neo4j:password@localhost:7687')
