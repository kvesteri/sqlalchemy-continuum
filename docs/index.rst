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


Reverting data
--------------

Transaction Log
===============



Configuration
=============


Alembic migrations
==================



Internals
=========


Extensions
==========

Flask
-----



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

