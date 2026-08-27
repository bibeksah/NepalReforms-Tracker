import os
import sys
import django

# Setup Django path
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from neomodel import db

def scrub_graph_noise():
    print("--- Starting Graph Scrubbing ---")
    
    # 1. Delete numeric-only titles (Page numbers)
    print("Deleting numeric noise...")
    db.cypher_query('MATCH (p:Project) WHERE p.title =~ "^[0-9\\s]*$" DETACH DELETE p')
    
    # 2. Delete symbol-only titles
    print("Deleting symbol noise...")
    db.cypher_query('MATCH (p:Project) WHERE p.title =~ "^[*|\\s]*$" DETACH DELETE p')
    
    # 3. Delete very short noise (less than 3 chars)
    print("Deleting short string noise...")
    db.cypher_query('MATCH (p:Project) WHERE size(p.title) < 3 DETACH DELETE p')
    
    # 4. Delete common header/metadata artifacts (Based on translations)
    print("Deleting metadata artifacts...")
    metadata_terms = [
        "Budget Head", "Section", "Sub-section", "Page Number", 
        "Table of Contents", "Annex", "Schedule", "Summary", 
        "Total", "Grand Total", "Sub Total", "Description"
    ]
    for term in metadata_terms:
        db.cypher_query('MATCH (p:Project) WHERE p.title CONTAINS $term DETACH DELETE p', {'term': term})

    print("--- Scrubbing Complete ---")

if __name__ == '__main__':
    scrub_graph_noise()
