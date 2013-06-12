class VersionedBuilder(object):
    def __init__(self, versioning_manager, model):
        self.manager = versioning_manager
        self.model = model
        self.attrs = self.model.__mapper__.class_manager.values()

    def option(self, name):
        try:
            return self.model.__versioned__[name]
        except (AttributeError, KeyError):
            return self.manager.DEFAULT_OPTIONS[name]
