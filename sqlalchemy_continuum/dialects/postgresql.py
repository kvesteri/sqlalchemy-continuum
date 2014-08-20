import sqlalchemy as sa

from sqlalchemy_continuum.plugins import PropertyModTrackerPlugin


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
        WHERE {end_transaction_column} IS NULL AND {primary_key_criteria}
    ) AND
    {primary_key_criteria};
"""


def uses_property_mod_tracking(manager):
    return any(
        isinstance(plugin, PropertyModTrackerPlugin)
        for plugin in manager.plugins
    )


class SQLConstruct(object):
    def __init__(
        self,
        table,
        transaction_column_name,
        operation_type_column_name,
        version_table_name_format,
        excluded_columns=None,
        update_validity_for_tables=None,
        use_property_mod_tracking=False,
        end_transaction_column_name=None,
    ):
        self.update_validity_for_tables = update_validity_for_tables
        self.operation_type_column_name = operation_type_column_name
        self.transaction_column_name = transaction_column_name
        self.end_transaction_column_name = end_transaction_column_name
        self.version_table_name_format = version_table_name_format
        self.use_property_mod_tracking = use_property_mod_tracking
        self.table = table
        self.excluded_columns = excluded_columns
        if update_validity_for_tables is None:
            self.update_validity_for_tables = []
        if self.excluded_columns is None:
            self.excluded_columns = []

    @property
    def table_name(self):
        if self.table.schema:
            return '%s."%s"' % (self.table.schema, self.table.name)
        else:
            return '"' + self.table.name + '"'

    @property
    def version_table_name(self):
        version_table_name = self.version_table_name_format % self.table.name
        if self.table.schema:
            version_table_name = '%s.%s' % (
                self.table.schema, version_table_name
            )
        return version_table_name

    @classmethod
    def for_manager(self, manager, cls):
        strategy = manager.option(cls, 'strategy')
        operation_type_column = manager.option(
            cls,
            'operation_type_column_name'
        )
        excluded_columns =  [
            c.name for c in cls.__table__.c
            if manager.is_excluded_column(cls, c)
        ]
        return self(
            update_validity_for_tables=(
                sa.inspect(cls).tables if strategy == 'validity' else []
            ),
            version_table_name_format=manager.option(cls, 'table_name'),
            operation_type_column_name=operation_type_column,
            transaction_column_name=manager.option(
                cls, 'transaction_column_name'
            ),
            end_transaction_column_name=manager.option(
                cls, 'end_transaction_column_name'
            ),
            use_property_mod_tracking=uses_property_mod_tracking(manager),
            excluded_columns=excluded_columns,
            table=cls.__table__
        )

    @property
    def columns(self):
        return [c for c in self.table.c if c.name not in self.excluded_columns]

    @property
    def columns_without_pks(self):
        return [c for c in self.columns if not c.primary_key]

    @property
    def pk_columns(self):
        return [c for c in self.columns if c.primary_key]

    def copy_args(self):
        return dict(
            (k, v) for k, v in self.__dict__.items() if not k.startswith('__')
        )


class UpsertSQL(SQLConstruct):
    builders = {
        'update_values': ', ',
        'insert_values': ', ',
        'column_names': ', ',
        'primary_key_criteria': ' AND ',
    }

    def __init__(self, *args, **kwargs):
        SQLConstruct.__init__(self, *args, **kwargs)

        for key in self.builders:
            setattr(self, key, getattr(self, 'build_%s' % key)())

    def build_column_names(self):
        column_names = ['"%s"' % c.name for c in self.columns]
        if self.use_property_mod_tracking:
            column_names += [
                '%s_mod' % c.name for c in self.columns_without_pks
            ]
        return column_names

    def build_primary_key_criteria(self):
        return [
            '"{name}" = NEW."{name}"'.format(name=c.name)
            for c in self.columns if c.primary_key
        ]

    def build_update_values(self):
        parent_columns = [
            '"{name}" = NEW."{name}"'.format(name=c.name)
            for c in self.columns
        ]
        mod_columns = []
        if self.use_property_mod_tracking:
            mod_columns = [
                '{0}_mod = NOT ((OLD.{0} IS NULL AND NEW.{0} IS NULL) '
                'OR (OLD.{0} = NEW.{0}))'.format(c.name)
                for c in self.columns_without_pks
            ]

        return (
            ['%s = 1' % self.operation_type_column_name] +
            parent_columns +
            mod_columns
        )

    def build_insert_values(self):
        values = self.build_values()
        if self.use_property_mod_tracking:
            values += self.build_mod_tracking_values()
        return values

    def build_values(self):
        return ['NEW."%s"' % c.name for c in self.columns]

    def build_mod_tracking_values(self):
        return []

    def __str__(self):
        params = dict(
            version_table_name=self.version_table_name,
            transaction_column=self.transaction_column_name,
            operation_type=self.operation_type,
            operation_type_column=self.operation_type_column_name
        )
        for key, join_operator in self.builders.items():
            params[key] = join_operator.join(getattr(self, key))

        sql = upsert_cte_sql.format(**params)
        return sql


class DeleteUpsertSQL(UpsertSQL):
    operation_type = 2

    def build_primary_key_criteria(self):
        return [
            '"{name}" = OLD."{name}"'.format(name=c.name)
            for c in self.pk_columns
        ]

    def build_mod_tracking_values(self):
        return ['True'] * len(self.columns_without_pks)

    def build_update_values(self):
        return [
            '"{name}" = OLD."{name}"'.format(name=c.name)
            for c in self.columns
        ]

    def build_values(self):
        return ['OLD."%s"' % c.name for c in self.columns]


class InsertUpsertSQL(UpsertSQL):
    operation_type = 0

    def build_mod_tracking_values(self):
        return ['True'] * len(self.columns_without_pks)


class UpdateUpsertSQL(UpsertSQL):
    operation_type = 1

    def build_mod_tracking_values(self):
        return [
            'NOT ((OLD."{0}" IS NULL AND NEW."{0}" IS NULL) '
            'OR (OLD."{0}" = NEW."{0}"))'
            .format(c.name) for c in self.columns_without_pks
        ]


class ValiditySQL(SQLConstruct):
    @property
    def primary_key_criteria(self):
        return ' AND '.join(
            '"{name}" = NEW."{name}"'.format(name=c.name)
            for c in self.pk_columns
        )

    def __str__(self):
        params = dict(
            version_table_name=self.version_table_name,
            transaction_column=self.transaction_column_name,
            end_transaction_column=self.end_transaction_column_name,
            primary_key_criteria=self.primary_key_criteria
        )
        return validity_sql.format(**params)


class InsertValiditySQL(ValiditySQL):
    pass


class UpdateValiditySQL(ValiditySQL):
    pass


class DeleteValiditySQL(ValiditySQL):
    @property
    def primary_key_criteria(self):
        return ' AND '.join(
            '{name} = OLD."{name}"'.format(name=c.name)
            for c in self.pk_columns
        )

def get_validity_sql(class_, tables, params):
    params = params.copy()
    del params['table']
    return ''.join(str(class_(table, **params)) for table in tables)


class CreateTriggerSQL(SQLConstruct):
    def __str__(self):
        return trigger_sql.format(
            trigger_name='%s_trigger' % self.table.name,
            table_name=self.table_name,
            procedure_name='%s_audit' % self.table.name
        )


class CreateTriggerFunctionSQL(SQLConstruct):
    def __str__(self):
        args = self.copy_args()
        tables = self.update_validity_for_tables
        after_insert = get_validity_sql(InsertValiditySQL, tables, args)
        after_update = get_validity_sql(UpdateValiditySQL, tables, args)
        after_delete = get_validity_sql(DeleteValiditySQL, tables, args)
        return procedure_sql.format(
            procedure_name='%s_audit' % self.table.name,
            after_insert=after_insert,
            after_update=after_update,
            after_delete=after_delete,
            upsert_insert=InsertUpsertSQL(**args),
            upsert_update=UpdateUpsertSQL(**args),
            upsert_delete=DeleteUpsertSQL(**args)
        )


def create_versioning_triggers(manager, cls):
    sa.event.listen(
        cls.__table__,
        'after_create',
        sa.schema.DDL(str(CreateTriggerFunctionSQL.for_manager(manager, cls)))
    )
    sa.event.listen(
        cls.__table__,
        'after_create',
        sa.schema.DDL(str(CreateTriggerSQL.for_manager(manager, cls)))
    )
    sa.event.listen(
        cls.__table__,
        'after_drop',
        sa.schema.DDL(
            'DROP FUNCTION IF EXISTS %s()' %
            '%s_audit' % cls.__table__.name,
        )
    )
