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


Version objects
===============

Querying
--------


You can query history models just like any other sqlalchemy declarative model.

::

    ArticleHistory = Article.__versioned__['class']

    session.query(ArticleHistory).filter_by(name=u'some name').all()


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


Transaction Log
===============


TransactionLog can be queried just like any other sqlalchemy declarative model.

::
    TransactionLog = Article.__versioned__['transaction_class']

    # find all transactions
    self.session.query(TransactionLog).all()



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


Alembic migrations
==================

::

    from alembic import op
    from sqlalchemy_continuum.alembic import OperationsProxy


    op = OperationsProxy(op)


    op.create_table(
        'article_history',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True)
        sa.Column('name', sa.Unicode(255))
        sa.Column('content', sa.UnicodeText)
    )



Internals
=========


Extensions
==========

Flask
-----


Writing own versioning extension
--------------------------------



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

