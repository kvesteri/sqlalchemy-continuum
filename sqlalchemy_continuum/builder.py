class VersionedBuilder(object):
    def __init__(self, versioning_manager, model):
        self.manager = versioning_manager
        self.model = model
        self.attrs = self.model.__mapper__.class_manager.values()

    def option(self, name):
        return self.manager.option(self.model, name)
