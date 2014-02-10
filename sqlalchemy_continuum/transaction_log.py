import sqlalchemy as sa
from sqlalchemy.ext.compiler import compiles


@compiles(sa.types.BigInteger, 'sqlite')
def compile_big_integer(element, compiler, **kw):
    return 'INTEGER'


class TransactionLogBase(object):
    id = sa.Column(sa.types.BigInteger, primary_key=True, autoincrement=True)
    issued_at = sa.Column(sa.DateTime)

    @property
    def entity_names(self):
        """
        Return a list of entity names that changed during this transaction.
        """
        return [changes.entity_name for changes in self.changes]

    @property
    def changed_entities(self):
        """
        Return all changed entities for this transaction log entry.

        Entities are returned as a dict where keys are entity classes and
        values lists of entitites that changed in this transaction.
        """
        tuples = set(self.manager.history_class_map.items())
        entities = []

        for class_, history_class in tuples:

            if class_.__name__ not in self.entity_names:
                continue

            try:
                value = getattr(
                    self,
                    self.manager.options['relation_naming_function'](
                        class_.__name__
                    )
                )
            except AttributeError:
                continue

            if value:
                entities.append((
                    history_class,
                    value
                ))
        return dict(entities)


class TransactionMetaBase(object):
    transaction_id = sa.Column(
        sa.BigInteger,
        primary_key=True
    )
    key = sa.Column(sa.Unicode(255), primary_key=True)
    value = sa.Column(sa.UnicodeText)


class TransactionChangesBase(object):
    transaction_id = sa.Column(
        sa.BigInteger,
        primary_key=True
    )
    entity_name = sa.Column(sa.Unicode(255), primary_key=True)
