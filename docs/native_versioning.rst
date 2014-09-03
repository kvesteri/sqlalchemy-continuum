Native versioning
=================

As of version 1.1 SQLAlchemy-Continuum supports native versioning for PostgreSQL dialect.
Native versioning creates SQL triggers for all versioned models. These triggers keep track of changes made to versioned models. Compared to object based versioning, native versioning has

* Much faster than regular object based versioning
* Minimal memory footprint when used alongside `create_tables=False` and `create_models=False` configuration options.
* More cumbersome database migrations, since triggers need to be updated also.

Usage
-----

For enabling native versioning you need to set `native_versioning` configuration option as `True`.

::

    make_versioned(options={'native_versioning': True})



Schema migrations
-----------------

When making schema migrations (for example adding new columns to version tables) you need to remember to call sync_trigger in order to keep the version trigger up-to-date.

::

    from sqlalchemy_continuum.dialects.postgresql import sync_trigger


    sync_trigger(conn, 'article_version')
