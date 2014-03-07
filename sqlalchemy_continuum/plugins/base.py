class Plugin(object):
    def __init__(self, manager):
        self.manager = manager

    def is_session_modified(self, session):
        return False

    def after_build_tx_class(self):
        pass

    def after_build_history_table_columns(self, table_builder, columns):
        pass

    def before_flush(self, uow, session):
        pass

    def before_create_history_objects(self, uow, session):
        pass

    def after_create_history_objects(self, uow, session):
        pass

    def after_create_history_object(self, uow, parent_obj, history_obj):
        pass

    def before_create_tx_object(self, uow, session):
        pass

    def after_create_tx_object(self, uow, session):
        pass

    def after_history_class_built(self, parent_cls, history_cls):
        pass

    def after_construct_changeset(self, history_obj, changeset):
        pass

    def __repr__(self):
        return '<%s>' % self.__class__.__name__


class PluginCollection(object):
    def __init__(self, plugins):
        self.plugins = plugins

    def __iter__(self):
        for plugin in self.plugins:
            yield plugin

    def __len__(self):
        return len(self.plugins)

    def __repr__(self):
        return '<%s>' % self.__class__.__name__

    def __getattr__(self, attr):
        def wrapper(*args, **kwargs):
            return [
                getattr(plugin, attr)(*args, **kwargs)
                for plugin in self.plugins
            ]
        return wrapper
