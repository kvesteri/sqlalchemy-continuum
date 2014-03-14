class ModelFactory(object):
    model_name = None

    def __call__(self, manager):
        """
        Create model class but only if it doesn't already exist
        in declarative model registry.
        """
        registry = manager.declarative_base._decl_class_registry
        if self.model_name not in registry:
            return self.create_class(manager)
        return registry[self.model_name]
