Changelog
---------

Here you can see the full list of changes between each SQLAlchemy-Continuum release.


0.3.11 (2013-06-18)
^^^^^^^^^^^^^^^^^^

- Single table inheritance support added


0.3.10 (2013-06-18)
^^^^^^^^^^^^^^^^^^

- Generated operation_type column not nullable by default


0.3.9 (2013-06-18)
^^^^^^^^^^^^^^^^^^

- Added drop_table trigger synchronization


0.3.8 (2013-06-18)
^^^^^^^^^^^^^^^^^^

- Autoincrementation automatically removed from reflected primary keys


0.3.7 (2013-06-18)
^^^^^^^^^^^^^^^^^^

- Added identifier quoting for all column names


0.3.6 (2013-06-18)
^^^^^^^^^^^^^^^^^^

- Identifier quoting for create_trigger_sql


0.3.5 (2013-06-12)
^^^^^^^^^^^^^^^^^^

- Added alembic operations proxy class


0.3.4 (2013-06-12)
^^^^^^^^^^^^^^^^^^

- VersioningManager now added in __versioned__ dict of each versioned class


0.3.3 (2013-06-12)
^^^^^^^^^^^^^^^^^^

- Creating TransactionLog now checks if it already exists.


0.3.2 (2013-06-12)
^^^^^^^^^^^^^^^^^^

- Added operation_type column to version tables.


0.3.1 (2013-06-12)
^^^^^^^^^^^^^^^^^^

- Versioned mixin no longer holds lists of pending objects
- Added VersioningManager for more customizable versioning syntax


0.3.0 (2013-06-10)
^^^^^^^^^^^^^^^^^^

- Model changesets
- Fixed previous and next accessors
- Updates generate versions only if actual changes occur


0.2.1 (2013-06-10)
^^^^^^^^^^^^^^^^^^

- Added sanity check in all_affected_entities


0.2.0 (2013-06-10)
^^^^^^^^^^^^^^^^^^

- Added backref relations to TransactionLog
- Added all_affected_entities property to TransactionLog


0.1.9 (2013-06-10)
^^^^^^^^^^^^^^^^^^

- Renamed internal attribute __pending__ to __pending_versioned__ in order to avoid variable naming collisions.


0.1.8 (2013-06-10)
^^^^^^^^^^^^^^^^^^

- Better checking of model table name in scenarios where model does not have __tablename__ defined.


0.1.7 (2013-06-07)
^^^^^^^^^^^^^^^^^^

- Added make_versioned for more robust declaration of versioned mappers


0.1.6 (2013-06-07)
^^^^^^^^^^^^^^^^^^

- Added PostgreSQLAdapter class


0.1.5 (2013-06-07)
^^^^^^^^^^^^^^^^^^

- Made trigger procedures table specific to allow more fine-grained control.


0.1.4 (2013-06-06)
^^^^^^^^^^^^^^^^^^

- Added column order inspection.


0.1.3 (2013-06-06)
^^^^^^^^^^^^^^^^^^

- Removed foreign key dependency from version table and transaction table


0.1.2 (2013-06-06)
^^^^^^^^^^^^^^^^^^

- Fixed packaging


0.1.1 (2013-06-06)
^^^^^^^^^^^^^^^^^^

- Initial support for join table inheritance


0.1.0 (2013-06-05)
^^^^^^^^^^^^^^^^^^

- Initial release
