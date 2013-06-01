from itertools import chain, izip
import sqlalchemy as sa
from .versioned import Versioned, configure_versioned

__all__ = (
    Versioned,
    configure_versioned
)


def versioned_objects(iterator):
    return [obj for obj in iterator if hasattr(obj, '__versioned__')]


def create_version(obj, transaction_obj, session):
    obj_mapper = sa.orm.object_mapper(obj)
    history_cls = obj.__versioned__['class']
    history_mapper = history_cls.__mapper__
    deleted = obj in session.deleted

    obj_state = sa.orm.attributes.instance_state(obj)
    attr = {}

    obj_changed = False
    zipped_iterator = izip(
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
            except sa.orm.exc.UnmappedColumnError:
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

            added, updated, deleted = sa.orm.attributes.get_history(
                obj, prop.key
            )
            #print added, updated, deleted
            if deleted:
                attr[hist_col.key] = deleted[0]
                obj_changed = True
            elif updated:
                attr[hist_col.key] = updated[0]
            else:
                # if the attribute had no value.
                attr[hist_col.key] = added[0]
                obj_changed = True

    many_to_many_properties = []

    # Check relationships
    for prop in obj_mapper.iterate_properties:
        if (
                isinstance(prop, sa.orm.RelationshipProperty) and
                sa.orm.attributes.get_history(obj, prop.key).has_changes()
        ):
            obj_changed = True
            if prop.secondary is not None:
                many_to_many_properties.append(prop)

    if not obj_changed and not deleted:
        return

    history_object = history_cls()
    history_object.transaction = transaction_obj
    for key, value in attr.iteritems():
        setattr(history_object, key, value)
    session.add(history_object)


def versioned_session(session):
    @sa.event.listens_for(session, 'before_flush')
    def before_flush(session, flush_context, instances):
        objects = versioned_objects(
            chain(session.new, session.dirty, session.deleted)
        )

        if objects:
            # Create one transaction object globally per transaction.
            transaction_class = objects[0].__versioned__['transaction_log']
            transaction_object = transaction_class()
            session.add(transaction_object)

    # SQLAlchemy sets relationship foreign key values after before_flush event,
    # hence we need to listen to after_flush event instead before_flush.
    @sa.event.listens_for(session, 'after_flush')
    def after_flush(session, flush_context):
        objects = versioned_objects(
            chain(session.new, session.dirty, session.deleted)
        )
        for obj in session.new:
            if obj.__table__.name == 'transaction_log':
                transaction_object = obj
                break

        for obj in objects:
            create_version(
                obj,
                transaction_object,
                session,
            )
