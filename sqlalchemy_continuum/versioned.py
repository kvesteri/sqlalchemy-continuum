class Versioned(object):
    HISTORY_CLASS_MAP = {}
    __versioned__ = {}
    __pending__ = []

    @classmethod
    def __declare_last__(cls):
        if not cls.__versioned__.get('class') and cls not in cls.__pending__:
            cls.__pending__.append(cls)
