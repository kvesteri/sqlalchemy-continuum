SQLAlchemy-Continuum
====================

SQLAlchemy-Continuum is a versioning extension for SQLAlchemy.

Why?
----

SQLAlchemy already has versioning extension. This extension however is very limited. It does not support versioning entire transactions.

Hibernate for Java has Envers, which is propably the most advanced database versioning tool out there. Ruby on Rails has `papertrail https://github.com/airblade/paper_trail`_, which has very nice API but lacks the efficiency and feature set of Envers.

As a Python/SQLAlchemy enthusiast I wanted to create a database versioning tool for Python with all the features of Envers and with as intuitive API as papertrail. Also I wanted to make it _fast_ keeping things as close to the database as possible (by using triggers and trigger procedures whenever possible).


Features
--------

* Does not store updates which don't change anything
* Uses database triggers for extremely fast versioning
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

    from sqlalchemy_continuum import make_versioned


    make_versioned()


    class Article(Base):
        __versioned__ = {}
        __tablename__ = 'user'

        id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
        name = sa.Column(sa.Unicode(255))
        content = sa.Column(sa.UnicodeText)



::

    Article.__versioned__['class']
    # ArticleHistory class

    Article.__versioned__['transaction_changes']
    # TransactionChanged class

    Article.__versioned__['transaction_log']
    # TransactionLog class


Version objects
===============


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
    self.session.query(TransactionLog).all()


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



Alembic migrations
==================

SQLAlchemy-Continuum relies heavily on database triggers and trigger procedures. Whenever your versioned model schemas are changed the associated triggers and trigger procedures would need to be changed too.

Gladly SQLAlchemy-Continuum provides tools to ease these kind of migrations. Only thing you need to do is add the following lines in your alembic migration files:


::

    from alembic import op
    from sqlalchemy_continuum.alembic import OperationsProxy


    op = OperationsProxy(op)


Now SQLAlchemy-Continuum is smart enough to regenerate triggers each time history tables are changed. So for example the following create_table call would update the associated triggers and trigger procedures.
::


    op.create_table(
        'article_history',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True)
        sa.Column('name', sa.Unicode(255))
        sa.Column('content', sa.UnicodeText)
    )



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

