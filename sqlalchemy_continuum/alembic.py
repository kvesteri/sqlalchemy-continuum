from sqlalchemy import Table, MetaData
from .drivers.postgresql import TableTriggerBuilder


class OperationsProxy(object):
    def __init__(self, operations):
        self.op = operations

    def _create_continuum_triggers(self, table_name):
        metadata = MetaData(bind=self.op.get_bind())
        table = Table(
            table_name,
            metadata,
            autoload=True
        )
        builder = TableTriggerBuilder(table)
        sql = builder.create_trigger_procedure_sql
        self.op.execute(sql)
        sql = builder.create_trigger_sql
        self.op.execute(sql)

    def _update_continuum_triggers(self, table_name):
        metadata = MetaData(bind=self.op.get_bind())
        table = Table(
            table_name,
            metadata,
            autoload=True
        )
        builder = TableTriggerBuilder(table)
        sql = builder.drop_trigger_procedure_sql
        self.op.execute(sql)

        sql = builder.create_trigger_procedure_sql
        self.op.execute(sql)

    def create_table(self, name, *columns, **kw):
        self.op.create_table(name, *columns, **kw)

        if '_history' in name:
            self._create_continuum_triggers(name)

    def add_column(self, table_name, column, schema=None):
        self.op.add_column(table_name, column, schema)

        if '_history' in table_name:
            self._update_continuum_triggers(table_name)

    def drop_column(self, table_name, column_name, **kw):
        self.op.drop_column(table_name, column_name, **kw)
        if '_history' in table_name:
            self._update_continuum_triggers(table_name)

    def __getattr__(self, name):
        return getattr(self.op, name)
