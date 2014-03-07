from sqlalchemy_continuum import UniqueBidict


class TestUniqueBidict(object):
    def test_inverse(self):
        bidict = UniqueBidict({1: -1, 2: -2})
        assert isinstance(bidict.inverse, UniqueBidict)
        assert isinstance(bidict.inverse.inverse, UniqueBidict)

    def test_eq(self):
        bidict = UniqueBidict({1: -1, 2: -2})
        assert bidict == UniqueBidict({1: -1, 2: -2})
        assert bidict == UniqueBidict({-1: 1, -2: 2})
        assert not (bidict == UniqueBidict({-1: 0, -2: 2}))

    def test_ne(self):
        bidict = UniqueBidict({1: -1, 2: -2})
        assert bidict != UniqueBidict({1: 0, 2: -2})
        assert bidict != UniqueBidict({-1: 0, -2: 2})

    def test_contains(self):
        bidict = UniqueBidict({1: -1, 2: -2})
        assert 1 in bidict
        assert 2 in bidict
        assert -1 in bidict
        assert -2 in bidict

    def test_setitem(self):
        bidict = UniqueBidict({1: -1, 2: -2})
        bidict[3] = -3
        assert 3 in bidict
        assert -3 in bidict

    def test_getitem(self):
        bidict = UniqueBidict({1: -1, 2: -2})
        assert bidict[1] == -1
        assert bidict[-1] == 1
        assert bidict[2] == -2
        assert bidict[-2] == 2
