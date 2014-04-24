Continuum Schema
================


Version tables
--------------

By default SQLAlchemy-Continuum creates a version table for each versioned entity table. The version tables are suffixed with '_version'. So for example if you have two versioned tables 'article' and 'category', SQLAlchemy-Continuum would create two version tables 'article_version' and 'category_version'.

By default the version tables contain these columns:

* id of the original entity (this can be more then one column in the case of composite primary keys)
* transaction_id - an integer that matches to the id number in the transaction_log table.
* end_transaction_id - an integer that matches the next version record's transaction_id. If this is the current version record then this field is null.
* operation_type - a small integer defining the type of the operation
* versioned fields from the original entity

If you are using :ref:`property-mod-tracker` Continuum also creates one boolean field for each versioned field. By default these boolean fields are suffixed with '_mod'.

The primary key of each version table is the combination of parent table's primary key + the transaction_id. This means there can be at most one version table entry for a given entity instance at given transaction.

Transaction tables
------------------

By default Continuum creates one transaction table called `transaction`. Many continuum plugins also create additional tables for efficient transaction storage. If you wish to query
efficiently transactions afterwards you should consider using some of these plugins.

The transaction table only contains two fields by default: id and issued_at.

Using vacuum
------------

.. module:: sqlalchemy_continuum
.. autofunction:: vacuum


Schema tools
------------

.. module:: sqlalchemy_continuum.schema

.. autofunction:: update_end_tx_column

.. autofunction:: update_property_mod_flags
