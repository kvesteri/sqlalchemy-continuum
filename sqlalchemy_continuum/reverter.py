#from itertools import chain
import sqlalchemy as sa
#from sqlalchemy_utils.functions import primary_keys
from .operation import Operation
from .utils import versioned_column_properties


def relationship_properties(class_):
    for prop in class_.__mapper__.iterate_properties:
        if isinstance(prop, sa.orm.RelationshipProperty):
            yield prop


def relationship_keys(class_):
    return map(lambda a: a.key, relationship_properties(class_))


class ReverterException(Exception):
    pass


class Reverter(object):
    def __init__(self, obj, visited_objects=[], relations=[]):
        self.visited_objects = visited_objects
        self.obj = obj
        self.version_parent = self.obj.version_parent
        self.parent_mapper = self.obj.__parent_class__.__mapper__
        self.parent_class = self.obj.__parent_class__
        self.relations = relations
        for path in relations:
            subpath = path.split('.')[0]
            if subpath not in relationship_keys(self.obj.__parent_class__):
                raise ReverterException(
                    "Could not initialize Reverter. Class '%s' does not have "
                    "relationship '%s'." % (
                        self.obj.__parent_class__.__name__,
                        subpath
                    )
                )

    def revert_properties(self):
        for prop in versioned_column_properties(self.parent_class):
            setattr(
                self.version_parent,
                prop.key,
                getattr(self.obj, prop.key)
            )

    def revert_relationships(self):
        for prop in self.parent_mapper.iterate_properties:
            if isinstance(prop, sa.orm.RelationshipProperty):
                if prop.key not in self.relations:
                    continue

                if prop.key in ['versions', 'transaction']:
                    continue

                if prop.secondary is not None:
                    setattr(self.version_parent, prop.key, [])
                    for value in getattr(self.obj, prop.key):
                        value = Reverter(value, self.visited_objects)()
                        if value:
                            getattr(self.version_parent, prop.key).append(
                                value
                            )
                else:
                    for value in getattr(self.obj, prop.key):
                        Reverter(value, self.visited_objects)()

    def __call__(self):
        if self.obj in self.visited_objects:
            return

        session = sa.orm.object_session(self.obj)

        if self.obj.operation_type == Operation.DELETE:
            session.delete(self.version_parent)
            return

        self.visited_objects.append(self.obj)

        # Check if parent object has been deleted
        if self.version_parent is None:
            self.version_parent = self.obj.__parent_class__()
            session.add(self.version_parent)

        # Before reifying relations we need to reify object properties. This
        # is needed because reifying relations might need to flush the session
        # which leads to errors when sqlalchemy tries to insert null values
        # into parent object (if parent object has not null constraints).
        self.revert_properties()
        self.revert_relationships()

        return self.version_parent
