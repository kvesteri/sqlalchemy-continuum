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

You can write your own versioning extension by extending the VersioningManager.


::


    from sqlalchemy_continuum import VersioningManager


    class MyVersioningManager(VersioningManager):
        pass
