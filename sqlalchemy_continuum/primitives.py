"""
This module defines an unique bijective dictionary which SQLAlchemy-Continuum
uses for mapping parent classes to history classes and vice versa.

Unique bijective dictionary for value pair sets X and Y has the following
charasteristics:

1. Each element of X must be paired with at least one element of Y,
2. No element of X may be paired with more than one element of Y,
3. Each element of Y must be paired with at least one element of X, and
4. No element of Y may be paired with more than one element of X.

And most importantly:

5. No value in X is contained in Y and no value in Y is contained X. In other
words the values of X and Y are both unique.

Some other bidict implementations:

http://code.activestate.com/recipes/576968/

http://code.activestate.com/recipes/578224/
"""


class UniqueBidict(dict):
    def __init__(self, *args, **kwargs):
        super(UniqueBidict, self).__init__(*args, **kwargs)
        self._inverse = dict.__new__(self.__class__)
        self._inverse.update(dict((v, k) for k, v in self.iteritems()))
        setattr(self._inverse, '_inverse', self)

    @property
    def inverse(self):
        return self._inverse

    def __eq__(self, other):
        return (
            super(UniqueBidict, self).__eq__(other) or
            super(UniqueBidict, self._inverse).__eq__(other)
        )

    def __setitem__(self, key, val):
        super(UniqueBidict, self).__setitem__(key, val)
        super(UniqueBidict, self._inverse).__setitem__(val, key)

    def __contains__(self, element):
        return (
            super(UniqueBidict, self).__contains__(element) or
            super(UniqueBidict, self._inverse).__contains__(element)
        )

    def __getitem__(self, key):
        try:
            return super(UniqueBidict, self).__getitem__(key)
        except KeyError:
            return super(UniqueBidict, self.inverse).__getitem__(key)
