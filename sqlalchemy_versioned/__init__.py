from itertools import chain

from .versioned import Versioned, configure_versioned

__all__ = (
    Versioned,
    configure_versioned
)


def versioned_objects(iterator):
    return [obj for obj in iterator if hasattr(obj, '__versioned__')]


def create_version(obj, transaction_obj, session, deleted=False):
    obj_mapper = object_mapper(obj)
    history_mapper = obj.__versioned__['class'].__mapper__
    history_cls = obj.__versioned__['class']

    obj_state = attributes.instance_state(obj)

    attr = {}

    obj_changed = False
    zipped_iterator = zip(
        obj_mapper.iterate_to_root(),
        history_mapper.iterate_to_root()
    )
    for om, hm in zipped_iterator:
        if hm.single:
            continue

        for hist_col in hm.local_table.c:
            if hist_col.key == 'transaction_id':
                continue

            obj_col = om.local_table.c[hist_col.key]

            # get the value of the
            # attribute based on the MapperProperty related to the
            # mapped column.  this will allow usage of MapperProperties
            # that have a different keyname than that of the mapped column.
            try:
                prop = obj_mapper.get_property_by_column(obj_col)
            except UnmappedColumnError:
                # in the case of single table inheritance, there may be
                # columns on the mapped table intended for the subclass only.
                # the "unmapped" status of the subclass column on the
                # base class is a feature of the declarative module as of sqla
                # 0.5.2.
                continue

            # expired object attributes and also deferred cols might not be in
            # the dict.  force it to load no matter what by using getattr().
            if prop.key not in obj_state.dict:
                getattr(obj, prop.key)

            a, u, d = attributes.get_history(obj, prop.key)

            if d:
                attr[hist_col.key] = d[0]
                obj_changed = True
            elif u:
                attr[hist_col.key] = u[0]
            else:
                # if the attribute had no value.
                attr[hist_col.key] = a[0]
                obj_changed = True

    if not obj_changed:
        # not changed, but we have relationships.  OK
        # check those too
        for prop in obj_mapper.iterate_properties:
            if (isinstance(prop, RelationshipProperty) and
                    attributes.get_history(obj, prop.key).has_changes()):
                obj_changed = True
                break

    if not obj_changed and not deleted:
        return

    history_object = history_cls()
    history_object.transaction = transaction_obj
    for key, value in attr.iteritems():
        setattr(history_object, key, value)
    session.add(history_object)


def versioned_session(session):
    @event.listens_for(session, 'before_flush')
    def before_flush(session, flush_context, instances):
        objects = versioned_objects(
            chain(session.new, session.dirty, session.deleted)
        )
        if objects:
            transaction_class = objects[0].__versioned__['transaction_log']
            transaction_object = transaction_class()
            session.add(transaction_object)

        for obj in objects:
            create_version(
                obj,
                transaction_object,
                session,
                obj in session.deleted
            )
