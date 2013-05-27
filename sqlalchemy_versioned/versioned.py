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

    pending_copy = copy(Versioned.__pending__)
    Versioned.__pending__ = []

    for cls in pending_copy:
        if cls in tables:
            builder = VersionedRelationshipBuilder(cls)
            builder.build_reflected_relationships()


class VersionedBuilder(object):
    DEFAULT_OPTIONS = {
        'base_classes': None,
        'table_name': '%s_history',
        'version_column_name': 'transaction_id',
    }

    def __init__(self, model):
        self.model = model
        self.attrs = self.model.__mapper__.class_manager.values()

    def option(self, name):
        try:
            return self.model.__versioned__[name]
        except (AttributeError, KeyError):
            return self.DEFAULT_OPTIONS[name]


class VersionedRelationshipBuilder(VersionedBuilder):
    def build_relationship_primaryjoin(self, property_):
        local_cls = self.model.__versioned__['class']
        remote_cls = property_.mapper.class_.__versioned__['class']

        condition = []
        for pair in property_.local_remote_pairs:
            condition.append(
                getattr(local_cls, pair[0].name) ==
                getattr(remote_cls, pair[1].name)
            )
        condition.append(local_cls.transaction_id == remote_cls.transaction_id)
        return sa.and_(*condition)

    def relationship_foreign_keys(self, property_):
        remote_cls = property_.mapper.class_.__versioned__['class']
        return [
            getattr(remote_cls, pair[1].name)
            for pair in property_.local_remote_pairs
        ]

    def build_reflected_relationships(self):
        for attr in self.attrs:
            if attr.key == 'versions':
                continue
            property_ = attr.property
            if isinstance(property_, sa.orm.RelationshipProperty):
                local_cls = self.model.__versioned__['class']
                remote_cls = property_.mapper.class_.__versioned__['class']

                setattr(
                    local_cls,
                    attr.key,
                    sa.orm.relationship(
                        remote_cls,
                        primaryjoin=self.build_relationship_primaryjoin(
                            property_
                        ),
                        foreign_keys=self.relationship_foreign_keys(
                            property_
                        )
                    )
                )


class VersionedTableBuilder(VersionedBuilder):
    @property
    def table_name(self):
        return self.option('table_name') % self.model.__tablename__

    def build_reflected_columns(self):
        columns = []
        for attr in self.attrs:
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


class VersionClassBase(object):
    def reify(self):
        for key, attr in self.__mapper__.class_manager.items():
            if key not in ['transaction', 'transaction_id']:
                setattr(self.parent, key, getattr(self, key))

    def deep_reify(self):
        self.reify()


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
            '%sHistory' % self.model.__name__,
            self.option('base_classes') + (VersionClassBase, ),
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
