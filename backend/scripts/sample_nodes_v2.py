import os
import sys
import django

sys.path.append(os.getcwd())
django.setup()

from tracker.graph_models import Project
from neomodel import db

# Look for nodes that likely contain real data (longer titles) and skip the metadata at the start
results, _ = db.cypher_query('MATCH (p:Project) WHERE size(p.title) > 10 RETURN p.title, p.title_ne SKIP 100 LIMIT 20')

print('--- Mid-Graph Node Content Sample ---')
for i, row in enumerate(results):
    print(f'Node {i+101}: title=\"{row[0]}\" | title_ne=\"{row[1]}\"')
