SQLAlchemy-Continuum
====================

|Build Status| |Version Status| |Downloads|

Versioning and auditing extension for SQLAlchemy.


Features
--------

- Creates versions for inserts, deletes and updates
- Does not store updates which don't change anything
- Supports alembic migrations
- Can revert objects data as well as all object relations at given transaction even if the object was deleted
- Transactions can be queried afterwards using SQLAlchemy query syntax
- Query for changed records at given transaction
- Temporal relationship reflection. Version object's relationship show the parent objects relationships as they where in that point in time.
- Supports native versioning for PostgreSQL database (trigger based versioning)


QuickStart
----------

::


    pip install SQLAlchemy-Continuum



In order to make your models versioned you need two things:

1. Call make_versioned() before your models are defined.
2. Add __versioned__ to all models you wish to add versioning to


.. code-block:: python


    from sqlalchemy_continuum import make_versioned


    make_versioned(user_cls=None)


    class Article(Base):
        __versioned__ = {}
        __tablename__ = 'article'

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
    article.versions[0].revert()

    article.name
    # u'Some article'


Resources
---------

- `Documentation <https://sqlalchemy-continuum.readthedocs.io/>`_
- `Issue Tracker <http://github.com/kvesteri/sqlalchemy-continuum/issues>`_
- `Code <http://github.com/kvesteri/sqlalchemy-continuum/>`_


.. image:: http://i.imgur.com/UFaRx.gif


.. |Build Status| image:: https://travis-ci.org/kvesteri/sqlalchemy-continuum.png?branch=master
   :target: https://travis-ci.org/kvesteri/sqlalchemy-continuum
.. |Version Status| image:: https://pypip.in/v/SQLAlchemy-Continuum/badge.png
   :target: https://pypi.python.org/pypi/SQLAlchemy-Continuum/
.. |Downloads| image:: https://pypip.in/d/SQLAlchemy-Continuum/badge.png
   :target: https://pypi.python.org/pypi/SQLAlchemy-Continuum/


More information
----------------

- http://en.wikipedia.org/wiki/Slowly_changing_dimension
- http://en.wikipedia.org/wiki/Change_data_capture
- http://en.wikipedia.org/wiki/Anchor_Modeling
- http://en.wikipedia.org/wiki/Shadow_table
- https://wiki.postgresql.org/wiki/Audit_trigger
- https://wiki.postgresql.org/wiki/Audit_trigger_91plus
- http://kosalads.blogspot.fi/2014/06/implement-audit-functionality-in.html
- https://github.com/2ndQuadrant/pgaudit
