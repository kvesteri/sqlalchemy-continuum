Native versioning
=================

As of version 1.1 SQLAlchemy-Continuum supports native versioning for PostgreSQL dialect.
Native versioning creates SQL triggers for all versioned models. These triggers keep track of changes made to versioned models. Compared to object based versioning, native versioning has

* Much faster than regular object based versioning
* Minimal memory footprint when used alongside `create_tables=False` and `create_models=False` configuration options.
* More cumbersome database migrations, since triggers need to be updated also.

Usage
-----

Just use `native_versioning=True` configuration option and create appropriate functions and triggers by using the :mod:`sqlalchemy_continuum.dialects.postgresql` module.

::

    make_versioned(options={'native_versioning': True})



::

    from sqlalchemy_continuum.dialects.postgresql import (
        CreateTriggerFunctionSQL, CreateTriggerSQL
    )

    function_sql = str(CreateTriggerFunctionSQL(my_versioned_table))
    session.execute(query)
    trigger_sql = str(CreateTriggerSQL(my_versioned_table))
    session.execute(query)
