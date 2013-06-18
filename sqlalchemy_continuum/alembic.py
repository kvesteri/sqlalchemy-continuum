from .drivers.postgresql import TriggerSynchronizer


class OperationsProxy(object):
    def __init__(self, operations):
        self.op = operations

    def synchronizer_factory(self, table_name):
        return TriggerSynchronizer(self.op, table_name)

    def create_table(self, name, *columns, **kw):
        self.op.create_table(name, *columns, **kw)

        if '_history' in name:
            self.synchronizer_factory(name).sync_create_table()

    def drop_table(self, name):
        if '_history' in name:
            self.synchronizer_factory(name).sync_drop_table()

        self.op.drop_table(name)

    def add_column(self, table_name, column, schema=None):
        self.op.add_column(table_name, column, schema)

        if '_history' in table_name:
            self.synchronizer_factory(table_name).sync_alter_table()

    def drop_column(self, table_name, column_name, **kw):
        self.op.drop_column(table_name, column_name, **kw)
        if '_history' in table_name:
            self.synchronizer_factory(table_name).sync_alter_table()

    def __getattr__(self, name):
        return getattr(self.op, name)
