from copy import copy
import sqlalchemy as sa
from sqlalchemy_utils.functions import primary_keys
from .builder import VersionedBuilder


class VersionClassBase(object):
    @property
    def previous(self):
        """
        Returns the previous version relative to this version in the version
        history.
        """
        if not self.parent:
            # parent object has been deleted
            return self._previous_query.first()
        return self.parent.versions[self.index - 1]

    @property
    def _previous_query(self):
        session = sa.orm.object_session(self)
        alias = sa.orm.aliased(self)
        subquery = (
            sa.select(
                [sa.func.max(alias.transaction_id)],
                from_obj=[alias.__table__]
            )
            .where(alias.transaction_id < self.transaction_id)
            .correlate(alias.__table__)
        )
        return (
            session.query(self.__class__)
            .filter(sa.and_(*self._pk_correlation_condition()))
            .filter(self.__class__.transaction_id == subquery)
        )

    def _pk_correlation_condition(self, skip_transaction_id=True):
        conditions = []
        for primary_key in primary_keys(self):
            if skip_transaction_id and primary_key.name == 'transaction_id':
                continue
            conditions.append(
                getattr(self, primary_key.name)
                ==
                getattr(self.__class__, primary_key.name)
            )
        return conditions

    @property
    def next(self):
        """
        Returns the next version relative to this version in the version
        history.
        """
        if not self.parent:
            # parent object has been deleted
            return self._next_query.first()
        return self.parent.versions[self.index + 1]

    @property
    def _next_query(self):
        session = sa.orm.object_session(self)

        alias = sa.orm.aliased(self)
        subquery = (
            sa.select(
                [sa.func.min(alias.transaction_id)],
                from_obj=[alias.__table__]
            )
            .where(alias.transaction_id > self.transaction_id)
            .correlate(alias.__table__)
        )
        return (
            session.query(self.__class__)
            .filter(sa.and_(*self._pk_correlation_condition()))
            .filter(self.__class__.transaction_id == subquery)
        )

    @property
    def _index_query(self):
        """
        Returns the query needed for fetching the index of this record relative
        to version history.
        """
        alias = sa.orm.aliased(self)
        subquery = (
            sa.select([sa.func.count('1')], from_obj=[alias.__table__])
            .where(alias.transaction_id < self.transaction_id)
            .correlate(alias.__table__)
            .label('position')
        )
        query = (
            sa.select([subquery], from_obj=[self.__table__])
            .where(sa.and_(*self._pk_correlation_condition(False)))
            .order_by(self.__class__.transaction_id)
        )
        return query

    @property
    def index(self):
        """
        Return the index of this version in the version history.
        """
        if not self.parent:
            # parent object has been deleted
            session = sa.orm.object_session(self)
            return session.execute(self._index_query).fetchone()[0]

        for index_, version in enumerate(self.parent.versions):
            if version == self:
                return index_

    def reify(self, visited_objects=[]):
        if self in visited_objects:
            return
        visited_objects.append(self)
        parent_mapper = self.__parent_class__.__mapper__

        # Check if parent object has been deleted
        if self.parent is None:
            self.parent = self.__parent_class__()

        for key, attr in parent_mapper.class_manager.items():
            if key not in ['versions', 'transaction', 'transaction_id']:
                if isinstance(attr.property, sa.orm.RelationshipProperty):
                    if attr.property.secondary is not None:
                        setattr(self.parent, key, [])
                        for value in getattr(self, key):
                            value = value.reify()
                            if value:
                                getattr(self.parent, key).append(
                                    value
                                )
                    else:
                        for value in getattr(self, key):
                            value.reify(visited_objects)
                else:
                    setattr(self.parent, key, getattr(self, key))
        return self.parent


class VersionedModelBuilder(VersionedBuilder):
    def build_parent_relationship(self):
        conditions = []
        foreign_keys = []
        for primary_key in primary_keys(self.model):
            conditions.append(
                getattr(self.model, primary_key.name)
                ==
                getattr(self.extension_class, primary_key.name)
            )
            foreign_keys.append(
                getattr(self.extension_class, primary_key.name)
            )

        self.model.versions = sa.orm.relationship(
            self.extension_class,
            primaryjoin=sa.and_(*conditions),
            foreign_keys=foreign_keys,
            lazy='dynamic',
            backref=sa.orm.backref('parent'),
            viewonly=True
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
