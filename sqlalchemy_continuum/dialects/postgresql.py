import sqlalchemy as sa

from sqlalchemy_continuum.plugins import PropertyModTrackerPlugin
from sqlalchemy_continuum.table_builder import ColumnReflector
from sqlalchemy_continuum.utils import get_versioning_manager, option


trigger_sql = """
CREATE TRIGGER {trigger_name}
AFTER INSERT OR UPDATE OR DELETE ON {table_name}
FOR EACH ROW EXECUTE PROCEDURE {procedure_name}()
"""

upsert_cte_sql = """
WITH upsert as
(
    UPDATE {version_table_name}
    SET {update_values}
    WHERE
        {transaction_column} = txid_current() AND
        {primary_key_criteria}
    RETURNING *
)
INSERT INTO {version_table_name}
({transaction_column}, {operation_type_column}, {column_names})
SELECT * FROM
    (VALUES (txid_current(), {operation_type}, {insert_values})) AS columns
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


def get_version_table_name(cls, table):
    manager = get_versioning_manager(cls)
    version_table_name = manager.option(cls, 'table_name') % table.name
    if table.schema:
        version_table_name = '%s.%s' % (table.schema, version_table_name)
    return version_table_name


class UpsertSQL(object):
    builders = {
        'update_values': ', ',
        'insert_values': ', ',
        'column_names': ', ',
        'primary_key_criteria': ' AND ',
    }

    def __init__(self, manager, cls, table):
        self.cls = cls
        self.table = table
        self.manager = manager
        self.operation_type_column = option(
            self.cls, 'operation_type_column_name'
        )
        reflector = ColumnReflector(manager, table, cls)
        self.columns = list(reflector.reflected_parent_columns)
        self.columns_without_pks = [
            c for c in self.columns if not c.primary_key
        ]
        self.pk_columns = [c for c in self.columns if c.primary_key]

        for key in self.builders:
            setattr(self, key, getattr(self, 'build_%s' % key)())

    def build_column_names(self):
        column_names = [c.name for c in self.columns]
        if uses_property_mod_tracking(self.manager):
            column_names += [
                '%s_mod' % c.name for c in self.columns_without_pks
            ]
        return column_names

    def build_primary_key_criteria(self):
        return [
            '{name} = NEW.{name}'.format(name=c.name)
            for c in self.columns if c.primary_key
        ]

    def build_update_values(self):
        parent_columns = tuple(
            '{name} = NEW.{name}'.format(name=c.name)
            for c in self.columns
        )
        mod_columns = tuple()
        if uses_property_mod_tracking(self.manager):
            mod_columns = tuple(
                '{0}_mod = NOT ((OLD.{0} IS NULL AND NEW.{0} IS NULL) '
                'OR (OLD.{0} = NEW.{0}))'.format(c.name)
                for c in self.columns_without_pks
            )

        return (
            ('%s = 1' % self.operation_type_column, ) +
            parent_columns +
            mod_columns
        )

    def build_insert_values(self):
        values = self.build_values()
        if uses_property_mod_tracking(self.manager):
            values += self.build_mod_tracking_values()
        return values

    def build_values(self):
        return ['NEW.%s' % c.name for c in self.columns]

    def build_mod_tracking_values(self):
        return []

    def __str__(self):
        params = dict(
            version_table_name=get_version_table_name(self.cls, self.table),
            transaction_column=self.manager.option(
                self.cls, 'transaction_column_name'
            ),
            operation_type=self.operation_type,
            operation_type_column=self.operation_type_column
        )
        for key, join_operator in self.builders.items():
            params[key] = join_operator.join(getattr(self, key))

        return upsert_cte_sql.format(**params)


class DeleteUpsertSQL(UpsertSQL):
    operation_type = 2

    def build_primary_key_criteria(self):
        return [
            '{name} = OLD.{name}'.format(name=c.name)
            for c in self.pk_columns
        ]

    def build_update_values(self):
        return [
            '{name} = OLD.{name}'.format(name=c.name)
            for c in self.columns
        ]

    def build_values(self):
        return ['OLD.%s' % c.name for c in self.columns]


class InsertUpsertSQL(UpsertSQL):
    operation_type = 0

    def build_mod_tracking_values(self):
        return ['True'] * len(self.columns_without_pks)


class UpdateUpsertSQL(UpsertSQL):
    operation_type = 1

    def build_mod_tracking_values(self):
        return [
            'NOT ((OLD.{0} IS NULL AND NEW.{0} IS NULL) '
            'OR (OLD.{0} = NEW.{0}))'
            .format(c.name) for c in self.columns_without_pks
        ]


class PostgreSQLTriggerBuilder(object):
    def __init__(self, manager):
        self.manager = manager

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
            upsert_insert=InsertUpsertSQL(self.manager, cls, table),
            upsert_update=UpdateUpsertSQL(self.manager, cls, table),
            upsert_delete=DeleteUpsertSQL(self.manager, cls, table)
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
