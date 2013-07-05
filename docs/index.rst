SQLAlchemy-Continuum
====================

SQLAlchemy-Continuum is a versioning extension for SQLAlchemy.

Why?
----

SQLAlchemy already has versioning extension. This extension however is very limited. It does not support versioning entire transactions.

Hibernate for Java has Envers, which is propably the most advanced database versioning tool out there. Ruby on Rails has `papertrail https://github.com/airblade/paper_trail`_, which has very nice API but lacks the efficiency and feature set of Envers.

As a Python/SQLAlchemy enthusiast I wanted to create a database versioning tool for Python with all the features of Envers and with as intuitive API as papertrail. Also I wanted to make it _fast_ keeping things as close to the database as possible.


Features
--------

* Does not store updates which don't change anything
* Supports alembic migrations
* Can revert objects data as well as all object relations at given transaction even if the object was deleted
* Transactions can be queried afterwards using SQLAlchemy query syntax
* Query for changed records at given transaction



Installation
------------


::


    pip install SQLAlchemy-Continuum


Basics
------

In order to make your models versioned you need two things:

1. Call make_versioned() before your models are defined.
2. Add __versioned__ to all models you wish to add versioning to


::


    import sqlalchemy as sa
    from sqlalchemy_continuum import make_versioned


    make_versioned()


    class Article(Base):
        __versioned__ = {}
        __tablename__ = 'user'

        id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
        name = sa.Column(sa.Unicode(255))
        content = sa.Column(sa.UnicodeText)


    # after you have defined all your models, call configure_mappers:
    sa.orm.configure_mappers()



::


    Article.__versioned__['class']
    # ArticleHistory class

    Article.__versioned__['transaction_changes']
    # TransactionChanged class

    Article.__versioned__['transaction_log']
    # TransactionLog class


Versions and transactions
-------------------------

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


Version objects
===============



Operation types
---------------

When changing entities and committing results into database Continuum saves the used
operations (INSERT, UPDATE or DELETE) into version entities. The operation types are stored
by default to a small integer field named 'operation_type'. Class called 'Operation' holds
convenient constants for these values as shown below:

::


    from sqlalchemy_continuum import Operation

    article = Article(name=u'Some article')
    session.add(article)
    session.commit()

    article.versions[0].operation_type == Operation.INSERT

    article.name = u'Some updated article'
    session.commit()
    article.versions[1].operation_type == Operation.UPDATE

    session.delete(article)
    session.commit()
    article.versions[2].operation_type == Operation.DELETE



Version traversal
-----------------

::

    first_version = article.versions[0]
    first_version.index
    # 0


    second_version = first_version.next
    assert second_version == article.versions[1]

    second_version.previous == first_version
    # True

    second_version.index
    # 1


Changelog
---------

Continuum provides easy way for getting the changelog of given version object. Each version contains a changelog
property which holds a dict of changed fields in that version.

::

    article = Article(name=u'New article', content=u'Some content')
    session.add(article)
    session.commit(article)

    version = article.versions[0]
    version.changelog
    # {
    #   'id': [None, 1],
    #   'name': [None, u'New article'],
    #   'content': [None, u'Some content']
    # }
    article.name = u'Updated article'
    session.commit()

    version = article.versions[1]
    version.changelog
    # {
    #   'name': [u'New article', u'Updated article'],
    # }

    session.delete(article)
    version = article.versions[1]
    version.changelog
    # {
    #   'id': [1, None]
    #   'name': [u'Updated article', None],
    #   'content': [u'Some content', None]
    # }


SQLAlchemy-Continuum also provides a utility function called changelog. With this function
you can easily check the changelog of given object in current transaction.


    from sqlalchemy_continuum import changelog


    article = Article(name=u'Some article')
    changelog(article)
    # {'name': [u'Some article', None]}




Reverting changes
-----------------

::

    article = Article(name=u'New article', content=u'Some content')
    session.add(article)
    session.commit(article)

    version = article.versions[0]
    article.name = u'Updated article'
    session.commit()

    version.reify()
    session.commit()

    article.name
    # u'New article'


Version relationships
---------------------

Each version object reflects all parent object relationships. Lets say you have two models: Article and Category. Each Article has one Category.

As you already know when making these models versioned, SQLAlchemy-Continuum creates two new declarative classes ArticleHistory and CategoryHistory.


::


    category = Category(name=u'Some category')
    article = Article(
        name=u'Some article',
        category=category
    )
    session.add(article)
    session.commit()


    session.delete(category)
    session.commit()

    # article no longer has category

    article.versions[0].reify()
    session.commit()

    article.category  # Category object





Querying
--------


You can query history models just like any other sqlalchemy declarative model.

::

    ArticleHistory = Article.__versioned__['class']

    session.query(ArticleHistory).filter_by(name=u'some name').all()




Transaction Log
===============


For each committed transaction SQLAlchemy-Continuum creates a new TransactionLog record.


TransactionLog can be queried just like any other sqlalchemy declarative model.

::
    TransactionLog = Article.__versioned__['transaction_class']

    # find all transactions
    session.query(TransactionLog).all()


Transaction contexts
--------------------

::

    from sqlalchemy_continuum import versioning_manager

    article = Article()
    session.add(article)

    with versioning_manager.tx_context(meta={'tags': 'article'})
        session.commit()


    # find all transactions with 'article' tags
    query = (
        session.query(TransactionLog)
        .filter(TransactionLog.meta['tags'] == 'article')
    )


Using lazy values in transaction context meta
---------------------------------------------

::

    from sqlalchemy_continuum import versioning_manager

    article = Article()
    session.add(article)

    with versioning_manager.tx_context(meta={'article_id': lambda: article.id})
        session.commit()


    # find all transactions where meta parameter article_id is given article id
    query = (
        session.query(TransactionLog)
        .filter(TransactionLog.meta['article_id'] == article.id)
    )


TransactionChanges
==================

In order to be able to to fetch efficiently entities that changed in given transaction SQLAlchemy-Continuum keeps track of changed entities in transaction_changes table.

This table has only two fields: transaction_id and entity_name. If for example transaction consisted of saving 5 new User entities and 1 Article entity, two new rows would be inserted into transaction_changes table.

================    =================
transaction_id          entity_name
----------------    -----------------
233678                  User
233678                  Article
================    =================



Find entities that changed in given transaction
-----------------------------------------------

    tx_log = self.session.query(TransactionLog).first()

    tx_log.changed_entities
    # dict of changed entities


Configuration
=============

Basic configuration options
---------------------------

Here is a full list of options that can be passed to __versioned__ attribute:

* base_classes (default: None)

* table_name (default: '%s_history')

* revision_column_name (default: 'revision')

* transaction_column_name (default: 'transaction_id')

* operation_type_column_name (default: 'operation_type')

* relation_naming_function (default: lambda a: pluralize(underscore(a)))


Example
::

    class Article(Base):
        __versioned__ = {
            'transaction_column_name': 'tx_id'
        }
        __tablename__ = 'user'

        id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
        name = sa.Column(sa.Unicode(255))
        content = sa.Column(sa.UnicodeText)


Customizing versioned mappers
-----------------------------

By default SQLAlchemy-Continuum versions all mappers. You can override this behaviour by passing the desired mapper class/object to make_versioned function.


::

    make_versioned(mapper=my_mapper)


Customizing versioned sessions
------------------------------


By default SQLAlchemy-Continuum versions all sessions. You can override this behaviour by passing the desired session class/object to make_versioned function.


::

    make_versioned(session=my_session)


Internals
=========

Continuum schema
----------------

By default SQLAlchemy-Continuum creates history tables for all versioned tables. So for example if you have two models Article and Category, SQLAlchemy-Continuum would create two history models ArticleHistory and CategoryHistory.



Extensions
==========

Flask
-----

    SQLAlchemy-Continuum comes with built-in extension for Flask. This extensions saves current user id as well as user remote address in transaction log.


::

    from sqlalchemy_continuum.ext.flask import FlaskVersioningManager
    from sqlalchemy_continuum import make_versioned


    make_versioned(manager=FlaskVersioningManager())



Writing own versioning extension
--------------------------------



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

