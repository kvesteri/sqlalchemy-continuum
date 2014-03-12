from sqlalchemy_continuum.plugins import PluginCollection


class TestPluginCollection(object):
    def test_init(self):
        assert PluginCollection([1, 2, 3]).plugins == [1, 2, 3]

    def test_iter(self):
        assert list(PluginCollection([1, 2, 3])) == [1, 2, 3]

    def test_len(self):
        assert len(PluginCollection()) == 0
        assert len(PluginCollection([1, 2, 3])) == 3

    def test_getitem(self):
        assert PluginCollection([1, 2])[0] == 1

    def test_setitem(self):
        coll = PluginCollection([1, 2])
        coll[0] = 2
        assert coll[0] == 2

    def test_delitem(self):
        coll = PluginCollection([1, 2])
        del coll[0]
        assert list(coll) == [2]

    def test_append(self):
        coll = PluginCollection([1, 2])
        coll.append(3)
        assert list(coll) == [1, 2, 3]

    def test_getattr(self):
        class MyPlugin(object):
            def some_action(self):
                return 4
        coll = PluginCollection([MyPlugin(), MyPlugin()])
        assert list(coll.some_action()) == [4, 4]
