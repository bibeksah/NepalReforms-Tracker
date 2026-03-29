from neomodel import StructuredNode, StringProperty, IntegerProperty, RelationshipTo

class Province(StructuredNode):
    name = StringProperty(unique_index=True, required=True)

class Project(StructuredNode):
    title = StringProperty(required=True)
    budget = IntegerProperty()
    located_in = RelationshipTo('Province', 'LOCATED_IN')

class ManifestoPromise(StructuredNode):
    text = StringProperty(required=True)
    fulfilled_by = RelationshipTo('Project', 'FULFILLED_BY')
