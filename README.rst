SQLAlchemy-Continuum
====================

Versioning and auditing extension for SQLAlchemy.


Features
--------

- Does not store updates which don't change anything
- Uses database triggers for extremely fast versioning
- Supports alembic migrations
- Can restore objects data as well as all object relations at given transaction even if the object was deleted
- Transactions can be queried afterwards using SQLAlchemy query syntax
- Query for changed records at given transaction


.. image:: http://replygif.net/i/1182.gif


QuickStart
----------

::

    from sqlalchemy_continuum import make_versioned


    make_versioned()


    class Article(Base):
        __versioned__ = {}
        __tablename__ = 'user'

        id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
        name = sa.Column(sa.Unicode(255))
        content = sa.Column(sa.UnicodeText)


    article = Article(name=u'Some article', content=u'Some content')
    session.add(article)
    session.commit()

    # article has now one version stored in database
    article.versions[0].name
    # u'Some article'

    article.name = u'Updated name'
    session.commit()

    article.versions[1].name
    # u'Updated name'


    # lets revert back to first version
    article.versions[0].reify()

    article.name
    # u'Some article'


.. image:: http://i.imgur.com/UFaRx.gif


Resources
---------

- `Documentation <http://sqlalchemy-continuum.readthedocs.org/>`_
- `Issue Tracker <http://github.com/kvesteri/sqlalchemy-continuum/issues>`_
- `Code <http://github.com/kvesteri/sqlalchemy-continuum/>`_
