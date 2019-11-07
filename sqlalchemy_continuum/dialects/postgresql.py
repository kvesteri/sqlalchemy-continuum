import sqlalchemy as sa

from sqlalchemy_continuum.plugins import PropertyModTrackerPlugin
import re


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
        {transaction_column} = transaction_id_value
        AND
        {primary_key_criteria}
    RETURNING *
)
INSERT INTO {version_table_name}
({transaction_column}, {operation_type_column}, {column_names})
SELECT
    transaction_id_value,
    {operation_type},
    {insert_values}
WHERE NOT EXISTS (SELECT 1 FROM upsert);
"""

temporary_transaction_sql = """
CREATE TEMP TABLE IF NOT EXISTS {temporary_transaction_table}
({transaction_table_columns})
ON COMMIT DELETE ROWS;
"""

insert_temporary_transaction_sql = """
INSERT INTO {temporary_transaction_table} ({transaction_table_columns})
VALUES ({transaction_values});
"""

temp_transaction_trigger_sql = """
CREATE TRIGGER transaction_trigger
AFTER INSERT ON {transaction_table}
FOR EACH ROW EXECUTE PROCEDURE transaction_temp_table_generator()
"""

procedure_sql = """
CREATE OR REPLACE FUNCTION {procedure_name}() RETURNS TRIGGER AS $$
DECLARE transaction_id_value INT;
BEGIN
    BEGIN
        transaction_id_value = (SELECT id FROM temporary_transaction);
    EXCEPTION WHEN others THEN
        RAISE EXCEPTION 'A {transaction_table_name} row was never created for this database transaction, so versioning cannot proceed.'
            USING HINT = 'Please create a row in {transaction_table_name} after opening a database transaction.';
    END;

    IF transaction_id_value IS NULL THEN
        RAISE EXCEPTION 'A {transaction_table_name} row was never created for this database transaction, so versioning cannot proceed.'
            USING HINT = 'Please create a row in {transaction_table_name} after opening a database transaction.';
    END IF;

    IF (TG_OP = 'INSERT') THEN
        {after_insert}
        {upsert_insert}
    ELSIF (TG_OP = 'UPDATE') THEN
        IF (hstore(NEW.*) - hstore(OLD.*) - ARRAY[{excluded_columns}]::text[])
            = hstore('')
        THEN
            RETURN NULL;
        END IF;
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
UPDATE {version_table_name}
SET {end_transaction_column} = transaction_id_value
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
        transaction_table_name='transaction',
    ):
        self.update_validity_for_tables = update_validity_for_tables
        self.operation_type_column_name = operation_type_column_name
        self.transaction_column_name = transaction_column_name
        self.end_transaction_column_name = end_transaction_column_name
        self.version_table_name_format = version_table_name_format
        self.use_property_mod_tracking = use_property_mod_tracking
        self.table = table
        self.excluded_columns = excluded_columns
        self.transaction_table_name = transaction_table_name
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
    def temporary_transaction_table_name(self):
        return 'temporary_transaction'

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
        excluded_columns = [
            c.name for c in sa.inspect(cls).columns
            if manager.is_excluded_column(cls, c)
        ]

        transaction_table_name = 'transaction'
        if manager.transaction_cls:
            transaction_table_name = manager.transaction_cls.__table__.name
            if manager.transaction_cls.__table__.schema:
                transaction_table_name = '%s.%s' % (manager.transaction_cls.__table__.schema, transaction_table_name)

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
            table=cls.__table__,
            transaction_table_name=transaction_table_name,
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
                '{0}_mod = {0}_mod OR OLD."{0}" IS DISTINCT FROM NEW."{0}"'
                .format(c.name)
                for c in self.columns_without_pks
            ]
        validity_strategy_columns = []
        if self.update_validity_for_tables:
            validity_strategy_columns = ['{0} = NULL'.format(self.end_transaction_column_name)]
        return (
            parent_columns +
            mod_columns +
            validity_strategy_columns
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
            operation_type_column=self.operation_type_column_name,
            transaction_table_name=self.transaction_table_name,
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
        parent_columns = [
            '"{name}" = OLD."{name}"'.format(name=c.name)
            for c in self.columns
        ]
        validity_strategy_columns = []
        if self.update_validity_for_tables:
            validity_strategy_columns = ['{0} = NULL'.format(self.end_transaction_column_name)]
        return parent_columns + validity_strategy_columns + ['%s = 2' % self.operation_type_column_name]

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
            'OLD."{0}" IS DISTINCT FROM NEW."{0}"'
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
            transaction_table_name=self.transaction_table_name,
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
        procedure_name = '%s_audit' % self.table.name
        if self.table.schema:
            procedure_name = '%s_%s' % (self.table.schema, procedure_name)

        return trigger_sql.format(
            trigger_name='%s_trigger' % self.table.name,
            table_name=self.table_name,
            procedure_name=procedure_name
        )


class TransactionSQLConstruct(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class CreateTemporaryTransactionTableSQL(TransactionSQLConstruct):
    table_name = 'temporary_transaction'

    def __str__(self):
        return temporary_transaction_sql.format(
            temporary_transaction_table=self.table_name,
            transaction_table_columns='id BIGINT, PRIMARY KEY(id)'
        )


class InsertTemporaryTransactionSQL(TransactionSQLConstruct):
    table_name = 'temporary_transaction'
    transaction_values = 'transaction_id_value'

    def __str__(self):
        return insert_temporary_transaction_sql.format(
            temporary_transaction_table=self.table_name,
            transaction_table_columns='id',
            transaction_values=self.transaction_values
        )


class CreateTriggerFunctionSQL(SQLConstruct):
    def __str__(self):
        args = self.copy_args()
        tables = self.update_validity_for_tables
        after_insert = get_validity_sql(InsertValiditySQL, tables, args)
        after_update = get_validity_sql(UpdateValiditySQL, tables, args)
        after_delete = get_validity_sql(DeleteValiditySQL, tables, args)

        procedure_name = '%s_audit' % self.table.name
        if self.table.schema:
            procedure_name = '%s_%s' % (self.table.schema, procedure_name)

        sql = procedure_sql.format(
            procedure_name=procedure_name,
            excluded_columns=', '.join(
                "'%s'" % c for c in self.excluded_columns
            ),
            transaction_table_name=self.transaction_table_name,
            after_insert=after_insert,
            after_update=after_update,
            after_delete=after_delete,
            temporary_transaction_sql=(
                CreateTemporaryTransactionTableSQL()
            ),
            insert_temporary_transaction_sql=(
                InsertTemporaryTransactionSQL()
            ),
            upsert_insert=InsertUpsertSQL(**args),
            upsert_update=UpdateUpsertSQL(**args),
            upsert_delete=DeleteUpsertSQL(**args)
        )
        return sql


class TransactionTriggerSQL(object):
    def __init__(self, tx_class):
        self.table = tx_class.__table__

    @property
    def transaction_table_name(self):
        if self.table.schema:
            return '%s.%s' % (self.table.schema, self.table.name)
        return self.table.name

    def __str__(self):
        return temp_transaction_trigger_sql.format(
            transaction_table=self.transaction_table_name
        )


def create_versioning_trigger_listeners(manager, cls):
    if not manager.options['create_trigger_listeners']:
        return
    
    compound_trigger_name = cls.__table__.name
    if cls.__table__.schema:
       compound_trigger_name = '%s_%s' % (cls.__table__.schema, compound_trigger_name) 

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
            '%s_audit' % compound_trigger_name,
        )
    )

def reverse_table_name_format(version_table_name_format):
    """
    Returns a regex that looks for a match where the version_table_name_format's %s is
    """
    return '^' + version_table_name_format.replace('%s', '(.*)') + '$'

DEFAULT_VERSION_TABLE_NAME_FORMAT = '%s_version'
def sync_trigger(conn,
                 table_name,
                 versioning_manager,
                 schema=None):
    """
    Synchronizes versioning trigger for given table with given connection.

    ::


        sync_trigger(conn, 'my_table')


    :param conn: SQLAlchemy connection object
    :param table_name: Name of the table to synchronize versioning trigger for
    :param versioning_manager: (Optional) the versioning manager

    .. versionadded: 1.1.0
    """
    custom_version_table_name_format = versioning_manager.options.get('table_name') if versioning_manager else None
    version_table_name_format = custom_version_table_name_format or DEFAULT_VERSION_TABLE_NAME_FORMAT
    parent_table_name_regex = reverse_table_name_format(version_table_name_format)
    
    meta = sa.MetaData(schema=schema)
    version_table = sa.Table(
        table_name,
        meta,
        autoload=True,
        autoload_with=conn
    )

    try:
        parent_table_name = re.findall(parent_table_name_regex, table_name)[0]
    except IndexError:
        raise ValueError('The version table name %s that was provided to sync_trigger does not conform to the format %s' % (table_name, version_table_name_format))

    parent_table = sa.Table(
        parent_table_name,
        meta,
        autoload=True,
        autoload_with=conn
    )
    excluded_columns = (
        set(c.name for c in parent_table.c) -
        set(c.name for c in version_table.c if not c.name.endswith('_mod'))
    )
    drop_trigger(conn, parent_table.name, parent_table.schema)
    create_trigger(conn,
                   table=parent_table,
                   versioning_manager=versioning_manager,
                   excluded_columns=excluded_columns)


def create_trigger(
    conn,
    table,
    versioning_manager,
    transaction_column_name='transaction_id',
    operation_type_column_name='operation_type',
    excluded_columns=None,
    use_property_mod_tracking=False,
    end_transaction_column_name='end_transaction_id',
):
    custom_version_table_name_format = versioning_manager.options.get('table_name') if versioning_manager else None
    version_table_name_format = custom_version_table_name_format or DEFAULT_VERSION_TABLE_NAME_FORMAT

    transaction_table_name = 'transaction'
    if versioning_manager.transaction_cls:
        transaction_table_name = versioning_manager.transaction_cls.__table__.name
        if versioning_manager.transaction_cls.__table__.schema:
            transaction_table_name = '%s.%s' % (versioning_manager.transaction_cls.__table__.schema, transaction_table_name)

    params = dict(
        table=table,
        update_validity_for_tables=[table],
        transaction_column_name=transaction_column_name,
        operation_type_column_name=operation_type_column_name,
        version_table_name_format=version_table_name_format,
        excluded_columns=excluded_columns,
        use_property_mod_tracking=uses_property_mod_tracking(versioning_manager) if versioning_manager else use_property_mod_tracking,
        end_transaction_column_name=end_transaction_column_name,
        transaction_table_name=transaction_table_name,
    )
    conn.execute(str(CreateTriggerFunctionSQL(**params)))
    conn.execute(str(CreateTriggerSQL(**params)))


def drop_trigger(conn, table_name, table_schema=None):
    compound_procedure_name = table_name
    schema = ''
    if table_schema:
        compound_procedure_name = '%s_%s' % (table_schema, table_name)
        schema = table_schema + '.'

    conn.execute(
        'DROP TRIGGER IF EXISTS %s_trigger ON %s"%s"' % (
            table_name,
            schema,
            table_name
        )
    )
    conn.execute('DROP FUNCTION IF EXISTS %s_audit()' % compound_procedure_name)
