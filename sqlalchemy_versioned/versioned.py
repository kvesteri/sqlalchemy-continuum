from copy import copy
import sqlalchemy as sa


class Versioned(object):
    __versioned__ = {}
    __pending__ = []

    @classmethod
    def __declare_last__(cls):
        if not cls.__versioned__.get('class'):
            cls.__pending__.append(cls)


def configure_versioned():
    tables = {}
    cls = None
    for cls in Versioned.__pending__:
        existing_table = None
        for class_ in tables:
            if issubclass(cls, class_):
                existing_table = tables[class_]
                break

        builder = VersionedTableBuilder(cls)
        if existing_table is not None:
            tables[class_] = builder.build_table(existing_table)
        else:
            table = builder.build_table()
            tables[cls] = table

    if cls:
        class TransactionLog(cls.__versioned__['base_classes'][0]):
            __tablename__ = 'transaction_log'
            id = sa.Column(sa.BigInteger, primary_key=True, autoincrement=True)
            issued_at = sa.Column(sa.DateTime)

    for cls in Versioned.__pending__:
        if cls in tables:
            builder = VersionedModelBuilder(cls)
            builder(tables[cls], TransactionLog)

    Versioned.__pending__ = []


class VersionedBuilder(object):
    DEFAULT_OPTIONS = {
        'base_classes': None,
        'table_name': '%s_history',
        'version_column_name': 'transaction_id',
    }

    def __init__(self, model):
        self.model = model

    def option(self, name):
        try:
            return self.model.__versioned__[name]
        except (AttributeError, KeyError):
            return self.DEFAULT_OPTIONS[name]


class VersionedTableBuilder(VersionedBuilder):
    def __init__(self, model):
        self.model = model

    @property
    def table_name(self):
        return self.option('table_name') % self.model.__tablename__

    def build_reflected_columns(self):
        columns = []
        for attr in self.model.__mapper__.class_manager.values():
            if not isinstance(attr.property, sa.orm.ColumnProperty):
                continue
            column = attr.property.columns[0]
            # Make a copy of the column so that it does not point to wrong
            # table.
            column_copy = column.copy()
            # Remove unique constraints
            column_copy.unique = False
            columns.append(column_copy)
        return columns

    def build_transaction_table_foreign_key(self):
        return sa.schema.ForeignKeyConstraint(
            [self.option('version_column_name')],
            ['transaction_log.id'],
            ondelete='CASCADE'
        )

    def build_version_column(self):
        return sa.Column(
            self.option('version_column_name'),
            sa.BigInteger,
            primary_key=True
        )

    def build_table(self, extends=None):
        items = []
        if extends is None:
            items.extend(self.build_reflected_columns())
            items.append(self.build_version_column())

        if extends is None:
            items.append(self.build_transaction_table_foreign_key())

        return sa.schema.Table(
            extends.name if extends is not None else self.table_name,
            self.model.__bases__[0].metadata,
            *items,
            extend_existing=extends is not None
        )


class VersionedModelBuilder(VersionedBuilder):
    def build_parent_relationship(self):
        self.model.versions = sa.orm.relationship(
            self.extension_class,
            primaryjoin=self.model.id == self.extension_class.id,
            foreign_keys=self.extension_class.id,
            lazy='dynamic',
            backref=sa.orm.backref('parent'),
        )

    def build_transaction_relationship(self, transaction_log_class):
        self.extension_class.transaction = sa.orm.relationship(
            transaction_log_class,
        )

    def build_model(self, table):
        if not self.option('base_classes'):
            raise Exception(
                'Missing __versioned__ base_classes option for model %s.'
                % self.model.__name__
            )
        return type(
            '%sTranslation' % self.model.__name__,
            self.option('base_classes'),
            {'__table__': table}
        )

    def __call__(self, table, transaction_log_class):
        # versioned attributes need to be copied for each child class,
        # otherwise each child class would share the same __versioned__
        # option dict
        self.model.__versioned__ = copy(self.model.__versioned__)
        self.model.__versioned__['transaction_log'] = transaction_log_class
        self.extension_class = self.build_model(table)
        self.build_parent_relationship()
        self.build_transaction_relationship(transaction_log_class)
        self.model.__versioned__['class'] = self.extension_class
        self.extension_class.__parent_class__ = self.model
