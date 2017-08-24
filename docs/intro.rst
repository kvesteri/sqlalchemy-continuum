Introduction
------------


Why?
^^^^

SQLAlchemy already has a versioning extension. This extension however is very limited. It does not support versioning entire transactions.

Hibernate for Java has Envers, which had nice features but lacks a nice API. Ruby on Rails has papertrail_, which has very nice API but lacks the efficiency and feature set of Envers.

As a Python/SQLAlchemy enthusiast I wanted to create a database versioning tool for Python with all the features of Envers and with as intuitive API as papertrail. Also I wanted to make it _fast_ keeping things as close to the database as possible.

.. _papertrail:  https://github.com/airblade/paper_trail


Features
^^^^^^^^

* Does not store updates which don't change anything
* Supports alembic migrations
* Can revert objects data as well as all object relations at given transaction even if the object was deleted
* Transactions can be queried afterwards using SQLAlchemy query syntax
* Querying for changed records at given transaction
* Querying for versions of entity that modified given property
* Querying for transactions, at which entities of a given class changed
* History models give access to parent objects relations at any given point in time



Installation
^^^^^^^^^^^^


::


    pip install SQLAlchemy-Continuum


Basics
^^^^^^

In order to make your models versioned you need two things:

1. Call make_versioned() before your models are defined.
2. Add __versioned__ to all models you wish to add versioning to


::


    import sqlalchemy as sa
    from sqlalchemy_continuum import make_versioned


    make_versioned()


    class Article(Base):
        __versioned__ = {}
        __tablename__ = 'article'

        id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
        name = sa.Column(sa.Unicode(255))
        content = sa.Column(sa.UnicodeText)


    # after you have defined all your models, call configure_mappers:
    sa.orm.configure_mappers()


After this setup SQLAlchemy-Continuum does the following things:

1. It creates ArticleHistory model that acts as version history for Article model
2. Creates TransactionLog and TransactionChanges models for transactional history tracking
3. Adds couple of listeners so that each Article object insert, update and delete gets recorded


When the models have been configured either by calling configure_mappers() or by accessing some of them the first time, the following things become available:


::

    from sqlalchemy_continuum import version_class, parent_class


    version_class(Article)  # ArticleHistory class

    parent_class(version_class(Article))  # Article class


Versions and transactions
^^^^^^^^^^^^^^^^^^^^^^^^^

At the end of each transaction SQLAlchemy-Continuum gathers all changes together and creates
version objects for each changed versioned entity. Continuum also creates one TransactionLog entity and
N number of TransactionChanges entities per transaction (here N is the number of affected classes per transaction).
TransactionLog and TransactionChanges entities are created for transaction tracking.


::


    article = Article(name=u'Some article')
    session.add(article)
    session.commit()

    article.versions[0].name == u'Some article'

    article.name = u'Some updated article'

    session.commit()

    article.versions[1].name == u'Some updated article'
