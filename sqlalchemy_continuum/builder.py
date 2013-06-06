class VersionedBuilder(object):
    DEFAULT_OPTIONS = {
        'base_classes': None,
        'table_name': '%s_history',
        'version_column_name': 'transaction_id',
        'inspect_column_order': False
    }

    def __init__(self, model):
        self.model = model
        self.attrs = self.model.__mapper__.class_manager.values()

    def option(self, name):
        try:
            return self.model.__versioned__[name]
        except (AttributeError, KeyError):
            return self.DEFAULT_OPTIONS[name]
