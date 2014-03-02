from copy import copy
import re
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
from functools import wraps
import six
import sqlalchemy as sa
from sqlalchemy_utils.functions import identity, has_changes
from .operation import Operation
from .utils import (
    is_versioned,
    is_modified,
    tx_column_name,
    end_tx_column_name
)


def tracked_operation(func):
    @wraps(func)
    def wrapper(self, mapper, connection, target):
        if not self.manager.options['versioning']:
            return
        if not is_versioned(target):
            return
        # We cannot use target._sa_instance_state.identity here since object's
        # identity is not yet updated at this phase
        key = (target.__class__, identity(target))

        return func(self, key, target)
    return wrapper


class UnitOfWork(object):
    def __init__(self, manager):
        self.manager = manager
        self.reset()

    def reset(self):
        """
        Reset the internal state of this UnitOfWork object. Normally this is
        called after transaction has been committed or rolled back.
        """
        self.current_transaction = None
        self.operations = OrderedDict()
        self._committing = False
        self.tx_context = {}
        self.tx_meta = {}
        self.pending_statements = []

    def track_operations(self, mapper):
        """
        Attach listeners for specified mapper that track SQL inserts, updates
        and deletes.

        :param mapper: mapper to track the SQL operations from
        """
        sa.event.listen(
            mapper, 'after_delete', self.track_deletes
        )
        sa.event.listen(
            mapper, 'after_update', self.track_updates
        )
        sa.event.listen(
            mapper, 'after_insert', self.track_inserts
        )

    def track_session(self, session):
        """
        Attach listeners that track the operations (flushing, committing and
        rolling back) of given session. This method should be used in
        conjuction with `track_operations`.

        :param session: SQLAlchemy session to track the operations from
        """
        sa.event.listen(
            session, 'before_flush', self.before_flush
        )
        sa.event.listen(
            session, 'before_commit', self.before_commit
        )
        sa.event.listen(
            session, 'after_commit', self.clear
        )
        sa.event.listen(
            session, 'after_rollback', self.clear
        )

    @tracked_operation
    def track_inserts(self, key, target):
        """
        Track object insert operations. Whenever object is inserted it is
        added to this UnitOfWork's internal operations dictionary.
        """
        if not is_modified(target):
            return
        if key in self.operations:
            # If the object is deleted and then inserted within the same
            # transaction we are actually dealing with an update.
            self.operations[key]['target'] = target
            self.operations[key]['operation_type'] = Operation.UPDATE
        else:
            self.operations[key] = {
                'target': target,
                'operation_type': Operation.INSERT
            }

    @tracked_operation
    def track_updates(self, key, target):
        """
        Track object update operations. Whenever object is updated it is
        added to this UnitOfWork's internal operations dictionary.
        """
        if not is_modified(target):
            return
        state_copy = copy(sa.inspect(target).committed_state)
        relationships = sa.inspect(target.__class__).relationships
        # Remove all ONETOMANY and MANYTOMANY relationships
        for rel_key, relationship in relationships.items():
            if relationship.direction.name in ['ONETOMANY', 'MANYTOMANY']:
                if rel_key in state_copy:
                    del state_copy[rel_key]

        if state_copy:
            self.operations[key] = {
                'target': target,
                'operation_type': Operation.UPDATE
            }

    @tracked_operation
    def track_deletes(self, key, target):
        """
        Track object deletion operations. Whenever object is deleted it is
        added to this UnitOfWork's internal operations dictionary.
        """
        self.operations[key] = {
            'target': target,
            'operation_type': Operation.DELETE
        }

    def create_history_objects(self, session):
        """
        Create history objects for given session based on operations collected
        by insert, update and deleted trackers.

        :param session: SQLAlchemy session object
        """
        if not self.manager.options['versioning']:
            return

        version_objs = []

        for key, value in copy(self.operations).items():
            version_obj = value['target'].__versioned__['class']()
            version_obj.operation_type = value['operation_type']

            if not self.current_transaction:
                raise Exception(
                    'Current transaction not available.'
                )
            setattr(
                version_obj,
                self.manager.option(
                    value['target'],
                    'transaction_column_name'
                ),
                self.current_transaction.id
            )
            version_obj.transaction = self.current_transaction
            self.assign_attributes(value['target'], version_obj)
            # The operation needs to be deleted before modifying the session
            del self.operations[key]
            version_objs.append(version_obj)

        for version_obj in version_objs:
            session.add(version_obj)
            self.update_version_validity(value['target'], version_obj)

    def version_validity_subquery(self, parent, version_obj):
        """
        Return the subquery needed by update_version_validity.

        This method is only used when using 'validity' versioning strategy.

        :param parent: SQLAlchemy declarative parent object
        :parem version_obj: SQLAlchemy declarative version object
        """
        fetcher = self.manager.fetcher(parent)
        session = sa.orm.object_session(version_obj)

        subquery = fetcher._transaction_id_subquery(
            version_obj, next_or_prev='prev'
        )
        if session.connection().engine.dialect.name == 'mysql':
            return sa.select(
                ['max_1'],
                from_obj=[
                    sa.sql.expression.alias(subquery, name='subquery')
                ]
            )
        return subquery

    def update_version_validity(self, parent, version_obj):
        """
        Updates previous version object end_transaction_id based on given
        parent object and newly created version object.

        This method is only used when using 'validity' versioning strategy.

        :param parent: SQLAlchemy declarative parent object
        :parem version_obj: SQLAlchemy declarative version object
        """
        if (
            self.manager.option(parent, 'strategy') ==
            'validity'
        ):
            fetcher = self.manager.fetcher(parent)
            session = sa.orm.object_session(version_obj)

            subquery = self.version_validity_subquery(parent, version_obj)
            query = (
                session.query(version_obj.__class__)
                .filter(
                    sa.and_(
                        getattr(
                            version_obj.__class__,
                            tx_column_name(version_obj)
                        ) == subquery,
                        *fetcher.parent_identity_correlation(version_obj)
                    )
                )
            )
            query.update(
                {
                    end_tx_column_name(version_obj):
                    self.current_transaction.id
                },
                synchronize_session=False
            )

    def create_association_versions(self, session):
        """
        Creates association table history records for given session.

        :param session: SQLAlchemy session object
        """
        for stmt in self.pending_statements:
            stmt = stmt.values(transaction_id=self.current_transaction.id)
            session.execute(stmt)

    def make_history(self, session):
        """
        Create transaction, transaction changes records, history objects.

        :param session: SQLAlchemy session object
        """
        if not self.manager.options['versioning']:
            return

        if self.current_transaction.id:
            self.create_association_versions(session)
            for plugin in self.manager.plugins:
                plugin.before_flush(self, session)

        self.create_history_objects(session)

    def should_create_transaction(self, session):
        """
        Return whether or not transaction entry should be created for given
        SQLAlchemy session object.

        :param session: SQLAlchemy session
        """
        return self.operations or self.pending_statements

    def changed_entities(self, session):
        """
        Return a set of changed versioned entities for given session.

        :param session: SQLAlchemy session object
        """
        changed_entities = set()
        for key, value in six.iteritems(self.operations):
            changed_entities.add(key[0])
        return changed_entities

    def before_flush(self, session, flush_context, instances):
        if not self.manager.options['versioning']:
            return

        if not self.current_transaction:
            attrs = {'issued_at': sa.func.now()}
            attrs.update(self.tx_context)
            self.current_transaction = self.manager.transaction_log_cls(
                **attrs
            )
            session.add(self.current_transaction)

    def before_commit(self, session):
        """
        SQLAlchemy before commit listener that marks the internal state of this
        UnitOfWork as committing. This state is later on used by after_flush
        listener which checks if the session is actually committing or if the
        flush occurs before session commit.

        :param session: SQLAlchemy session object
        """
        if not self.manager.options['versioning']:
            return

        self._committing = True
        # Flush is needed before updating history.
        session.flush()
        self.make_history(session)

    def clear(self, session):
        """
        Simple SQLAlchemy listener that is being invoked after succesful
        transaction commit or when transaction rollback occurs. The purpose of
        this listener is to reset this UnitOfWork back to its initialization
        state.

        :param session: SQLAlchemy session object
        """
        self.reset()

    def append_association_operation(self, conn, table_name, params, op):
        """
        Append history association operation to pending_statements list.
        """
        params['operation_type'] = op
        stmt = (
            self.manager.metadata.tables[table_name + '_history']
            .insert()
            .values(params)
        )
        self.pending_statements.append(stmt)

    def track_association_operations(
        self, conn, cursor, statement, parameters, context, executemany
    ):
        """
        Track association operations and adds the generated history
        association operations to pending_statements list.
        """
        if not self.manager.options['versioning']:
            return

        op = None

        if context.isinsert:
            op = Operation.INSERT
        elif context.isdelete:
            op = Operation.DELETE

        if op is not None:
            table_name = statement.split(' ')[2]
            table_names = [
                table.name for table in self.manager.association_tables
            ]
            if table_name in table_names:
                if executemany:
                    # SQLAlchemy does not support function based values for
                    # multi-inserts, hence we need to convert the orignal
                    # multi-insert into batch of normal inserts
                    for params in parameters:
                        self.append_association_operation(
                            conn,
                            table_name,
                            self.positional_args_to_dict(
                                op, statement, params
                            ),
                            op
                        )
                else:
                    self.append_association_operation(
                        conn,
                        table_name,
                        self.positional_args_to_dict(
                            op,
                            statement,
                            parameters
                        ),
                        op
                    )

    def positional_args_to_dict(self, op, statement, params):
        """
        On some drivers (eg sqlite) generated INSERT statements use positional
        args instead of key value dictionary. This method converts positional
        args to key value dict.

        :param statement: SQL statement string
        :param params: tuple or dict of statement parameters
        """
        if isinstance(params, tuple):
            parameters = {}
            if op == Operation.DELETE:
                regexp = '^DELETE FROM (.+?) WHERE'
                match = re.match(regexp, statement)
                tablename = match.groups()[0].strip('"').strip("'").strip('`')
                table = self.manager.metadata.tables[tablename]
                columns = table.primary_key.columns.values()
                for index, column in enumerate(columns):
                    parameters[column.name] = params[index]
            else:
                columns = [
                    column.strip() for column in
                    statement.split('(')[1].split(')')[0].split(',')
                ]
                for index, column in enumerate(columns):
                    parameters[column] = params[index]
            return parameters
        return params

    def should_nullify_attr(self, version_obj, attr):
        """
        Return whether or not given attribute of given version object should
        be nullified (set to None) at the end of the transaction.

        :param version_obj:
            Version object to check the attribute nullification
        :paremt attr:
            SQLAlchemy InstrumentedAttribute object
        """
        parent = version_obj.__parent_class__
        return (
            not self.manager.option(parent, 'store_data_at_delete') and
            version_obj.operation_type == Operation.DELETE and
            not attr.property.columns[0].primary_key and
            attr.key !=
            self.manager.option(
                parent,
                'transaction_column_name'
            )
        )

    def assign_attributes(self, parent_obj, version_obj):
        """
        Assign attributes values from parent object to version object. If the
        parent object is deleted this method assigns None values to all version
        object's attributes.

        :param parent_obj:
            Parent object to get the attribute values from
        :param version_obj:
            Version object to assign the attribute values to
        """
        excluded_attributes = self.manager.option(parent_obj, 'exclude')
        for attr_name, attr in parent_obj._sa_class_manager.items():
            if attr_name in excluded_attributes:
                continue
            if isinstance(attr.property, sa.orm.ColumnProperty):
                if self.should_nullify_attr(version_obj, attr):
                    value = None
                else:
                    value = getattr(parent_obj, attr_name)
                    self.assign_modified_flag(
                        parent_obj, version_obj, attr_name
                    )

                setattr(version_obj, attr_name, value)

    def assign_modified_flag(self, parent_obj, version_obj, attr_name):
        """
        Assign modified flag for given attribute of given version model object
        based on the modification state of this property in given parent model
        object.

        :param parent_obj:
            Parent object to check the modification state of given attribute
        :param version_obj:
            Version object to assign the modification flag into
        :param attr_name:
            Name of the attribute to check the modification state
        """
        if (
            self.manager.option(parent_obj, 'track_property_modifications')
            and
            has_changes(parent_obj, attr_name)
        ):
            setattr(
                version_obj,
                attr_name + self.manager.option(
                    parent_obj,
                    'modified_flag_suffix'
                ),
                True
            )
