SQLAlchemy-Continuum
====================

|Build Status| |Version Status| |Downloads|

This is Trialspark's fork of SQLALchemy Continuum. A versioning and auditing extension for SQLAlchemy.

Trialspark Features
-------------------
- Handles PostgreSQL Schemas
- Adds indices to Columns that are marked primary_key=True


Set up for publishing
---------------------
* Copy the following:

::

   [distutils]
   index-servers=
       testpypi
       pypi

   [testpypi]
   repository = https://test.pypi.org/legacy/
   username = rrmurcek
   password =

   [pypi]
   username = rrmurcek
   password =

* Paste into your local pypiprc:

::

   pbpaste > ~/.pypirc

* Set the password from 1pass

Publishing
----------

* Install twine, if you haven't already

::

   pip install twine

* Bump version number in setup.py, if necessary!

* Upload to our test pypi

::

   twine upload dist/* -r testpypi

* Verify that the new version appears here: https://test.pypi.org/project/SQLAlchemy-Continuum-Trialspark/
* Upload to our prod pypi

::

   twine upload dist/*

* Update requirements.txt in spark, if you released a new version


QuickStart
----------

::


    pip install SQLAlchemy-Continuum-Trialspark
