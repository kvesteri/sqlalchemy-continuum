from copy import copy

import sqlalchemy as sa
from sqlalchemy_utils.functions import get_declarative_base

from .model_builder import ModelBuilder
from .plugins import PropertyModTrackerPlugin
from .relationship_builder import RelationshipBuilder
from .table_builder import TableBuilder, ColumnReflector


trigger_sql = """
CREATE TRIGGER {trigger_name}
AFTER INSERT OR UPDATE OR DELETE ON {table_name}
FOR EACH ROW EXECUTE PROCEDURE {procedure_name}()
"""

upsert_cte_sql = """
WITH upsert as
(
    UPDATE {version_table_name}
    SET {update_columns}
    WHERE
        {transaction_column} = txid_current() AND
        {primary_key_condition}
    RETURNING *
)
INSERT INTO {version_table_name}
({transaction_column}, {operation_type_column}, {columns})
SELECT * FROM
    (VALUES (txid_current(), {operation_type}, {values})) AS columns
WHERE NOT EXISTS (SELECT 1 FROM upsert);
"""


procedure_sql = """
CREATE OR REPLACE FUNCTION {procedure_name}() RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'INSERT') THEN
        {after_insert}
        {upsert_insert}
    ELSIF (TG_OP = 'UPDATE') THEN
        {after_update}
        {upsert_update}
    ELSIF (TG_OP = 'DELETE') THEN
        {after_delete}
        {upsert_delete}
    END IF;
    RETURN NEW;
END;
$$
LANGUAGE plpgsql
"""

validity_sql = """
UPDATE {version_table_name} SET {end_transaction_column} = txid_current()
WHERE
    {transaction_column} = (
        SELECT MIN({transaction_column}) FROM {version_table_name}
        WHERE {end_transaction_column} IS NULL AND {primary_key_condition}
    ) AND
    {primary_key_condition};
"""


def uses_property_mod_tracking(manager):
    return any(
        isinstance(plugin, PropertyModTrackerPlugin)
        for plugin in manager.plugins
    )


class Builder(object):
    def trigger_ddl(self, cls):
        table = cls.__table__
        if table.schema:
            table_name = '%s."%s"' % (table.schema, table.name)
        else:
            table_name = '"' + table.name + '"'
        return sa.schema.DDL(
            trigger_sql.format(
                trigger_name='%s_trigger' % table.name,
                table_name=table_name,
                procedure_name='%s_audit' % table.name
            )
        )

    def upsert_sql(self, cls, operation_type):
        table = cls.__table__
        version_table_name = (
            self.manager.option(cls, 'table_name') % table.name
        )
        if table.schema:
            version_table_name = '%s.%s' % (table.schema, version_table_name)

        reflector = ColumnReflector(self.manager, table, cls)
        columns = list(reflector.reflected_parent_columns)
        columns_without_pks = [c for c in columns if not c.primary_key]
        operation_type_column = self.manager.option(
            cls, 'operation_type_column_name'
        )
        column_names = [c.name for c in columns]
        if uses_property_mod_tracking(self.manager):
            column_names += [
                '%s_mod' % c.name for c in columns_without_pks
            ]

        if operation_type == 2:
            values = ', '.join('OLD.%s' % c.name for c in columns)
            primary_key_condition = ' AND '.join(
                '{name} = OLD.{name}'.format(name=c.name)
                for c in columns if c.primary_key
            )
            update_columns = ', '.join(
                '{name} = OLD.{name}'.format(name=c.name)
                for c in columns
            )
        else:
            values = ['NEW.%s' % c.name for c in columns]
            if uses_property_mod_tracking(self.manager):
                if operation_type == 1:
                    values += [
                        'NOT ((OLD.{0} IS NULL AND NEW.{0} IS NULL) '
                        'OR (OLD.{0} = NEW.{0}))'.format(c.name)
                        for c in columns_without_pks
                    ]
                else:
                    values += ['True'] * len(columns_without_pks)
            values = ', '.join(values)

            primary_key_condition = ' AND '.join(
                '{name} = NEW.{name}'.format(name=c.name)
                for c in columns if c.primary_key
            )
            parent_columns = tuple(
                '{name} = NEW.{name}'.format(name=c.name)
                for c in columns
            )
            mod_columns = tuple()
            if uses_property_mod_tracking(self.manager):
                mod_columns = tuple(
                    '{0}_mod = NOT ((OLD.{0} IS NULL AND NEW.{0} IS NULL) '
                    'OR (OLD.{0} = NEW.{0}))'.format(c.name)
                    for c in columns_without_pks
                )

            update_columns = ', '.join(
                ('%s = 1' % operation_type_column, ) +
                parent_columns +
                mod_columns
            )

        return upsert_cte_sql.format(
            version_table_name=version_table_name,
            transaction_column=self.manager.option(
                cls, 'transaction_column_name'
            ),
            operation_type_column=operation_type_column,
            columns=', '.join(column_names),
            values=values,
            update_columns=update_columns,
            operation_type=operation_type,
            primary_key_condition=primary_key_condition
        )

    def get_version_table_name(self, cls, table):
        version_table_name = (
            self.manager.option(cls, 'table_name') % table.name
        )
        if table.schema:
            version_table_name = '%s.%s' % (table.schema, version_table_name)
        return version_table_name

    def trigger_function_ddl(self, cls):
        table = cls.__table__
        reflector = ColumnReflector(self.manager, table, cls)
        columns = list(reflector.reflected_parent_columns)

        update_primary_key_condition = ' AND '.join(
            '{name} = NEW.{name}'.format(name=c.name)
            for c in columns if c.primary_key
        )
        delete_primary_key_condition = ' AND '.join(
            '{name} = OLD.{name}'.format(name=c.name)
            for c in columns if c.primary_key
        )
        after_delete = ''
        after_insert = ''
        after_update = ''

        if self.manager.option(cls, 'strategy') == 'validity':
            for table in sa.inspect(cls).tables:
                version_table_name = self.get_version_table_name(cls, table)
                sql = validity_sql.format(
                    version_table_name=version_table_name,
                    end_transaction_column=self.manager.option(
                        cls, 'end_transaction_column_name'
                    ),
                    transaction_column=self.manager.option(
                        cls, 'transaction_column_name'
                    ),
                    primary_key_condition=update_primary_key_condition
                )
                after_insert += sql
                after_update += sql
                after_delete += validity_sql.format(
                    version_table_name=version_table_name,
                    end_transaction_column=self.manager.option(
                        cls, 'end_transaction_column_name'
                    ),
                    transaction_column=self.manager.option(
                        cls, 'transaction_column_name'
                    ),
                    primary_key_condition=delete_primary_key_condition
                )

        sql = procedure_sql.format(
            procedure_name='%s_audit' % table.name,
            after_insert=after_insert,
            after_update=after_update,
            after_delete=after_delete,
            upsert_insert=self.upsert_sql(cls, 0),
            upsert_update=self.upsert_sql(cls, 1),
            upsert_delete=self.upsert_sql(cls, 2)
        )
        return sa.schema.DDL(sql)

    def add_native_versioning_triggers(self, cls):
        sa.event.listen(
            cls.__table__,
            'after_create',
            self.trigger_function_ddl(cls)
        )
        sa.event.listen(
            cls.__table__,
            'after_create',
            self.trigger_ddl(cls)
        )
        sa.event.listen(
            cls.__table__,
            'after_drop',
            sa.schema.DDL(
                'DROP FUNCTION IF EXISTS %s()' %
                '%s_audit' % cls.__table__.name,
            )
        )

    def build_tables(self):
        """
        Build tables for version models based on classes that were collected
        during class instrumentation process.
        """
        processed_tables = set()
        for cls in self.manager.pending_classes:
            if not self.manager.option(cls, 'versioning'):
                continue

            if self.manager.options['native_versioning']:
                if cls.__table__ not in processed_tables:
                    self.add_native_versioning_triggers(cls)
                    processed_tables.add(cls.__table__)

            inherited_table = None
            for class_ in self.manager.tables:
                if (issubclass(cls, class_) and
                        cls.__table__ == class_.__table__):
                    inherited_table = self.manager.tables[class_]
                    break

            builder = TableBuilder(
                self.manager,
                cls.__table__,
                model=cls
            )
            if inherited_table is not None:
                self.manager.tables[class_] = builder(inherited_table)
            else:
                table = builder()
                self.manager.tables[cls] = table

    def closest_matching_table(self, model):
        """
        Returns the closest matching table from the generated tables dictionary
        for given model. First tries to fetch an exact match for given model.
        If no table was found then tries to match given model as a subclass.

        :param model: SQLAlchemy declarative model class.
        """
        if model in self.manager.tables:
            return self.manager.tables[model]
        for cls in self.manager.tables:
            if issubclass(model, cls):
                return self.manager.tables[cls]

    def build_models(self):
        """
        Build declarative version models based on classes that were collected
        during class instrumentation process.
        """
        if self.manager.pending_classes:
            cls = self.manager.pending_classes[0]
            self.manager.declarative_base = get_declarative_base(cls)
            self.manager.create_transaction_model()
            self.manager.plugins.after_build_tx_class(self.manager)

            for cls in self.manager.pending_classes:
                if not self.manager.option(cls, 'versioning'):
                    continue

                table = self.closest_matching_table(cls)
                if table is not None:
                    builder = ModelBuilder(self.manager, cls)
                    version_cls = builder(
                        table,
                        self.manager.transaction_cls
                    )

                    self.manager.plugins.after_version_class_built(
                        cls,
                        version_cls
                    )

        self.manager.plugins.after_build_models(self.manager)

    def build_relationships(self, version_classes):
        """
        Builds relationships for all version classes.

        :param version_classes: list of generated version classes
        """
        for cls in version_classes:
            if not self.manager.option(cls, 'versioning'):
                continue

            for prop in sa.inspect(cls).iterate_properties:
                if prop.key == 'versions':
                    continue
                builder = RelationshipBuilder(self.manager, cls, prop)
                builder()

    def instrument_versioned_classes(self, mapper, cls):
        """
        Collect versioned class and add it to pending_classes list.

        :mapper mapper: SQLAlchemy mapper object
        :cls cls: SQLAlchemy declarative class
        """
        if not self.manager.options['versioning']:
            return

        if hasattr(cls, '__versioned__'):
            if (not cls.__versioned__.get('class')
                    and cls not in self.manager.pending_classes):
                self.manager.pending_classes.append(cls)
                self.manager.metadata = cls.metadata

        if hasattr(cls, '__version_parent__'):
            parent = cls.__version_parent__
            self.manager.version_class_map[parent] = cls
            self.manager.parent_class_map[cls] = parent
            del cls.__version_parent__

    def configure_versioned_classes(self):
        """
        Configures all versioned classes that were collected during
        instrumentation process. The configuration has 4 steps:

        1. Build tables for version models.
        2. Build the actual version model declarative classes.
        3. Build relationships between these models.
        4. Empty pending_classes list so that consecutive mapper configuration
           does not create multiple version classes
        5. Assign all versioned attributes to use active history.
        """
        if not self.manager.options['versioning']:
            return

        self.build_tables()
        self.build_models()

        # Create copy of all pending versioned classes so that we can inspect
        # them later when creating relationships.
        pending_copy = copy(self.manager.pending_classes)
        self.manager.pending_classes = []
        self.build_relationships(pending_copy)

        for cls in pending_copy:
            # set the "active_history" flag
            for prop in sa.inspect(cls).iterate_properties:
                getattr(cls, prop.key).impl.active_history = True
