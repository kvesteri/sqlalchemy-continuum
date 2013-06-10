Changelog
---------

Here you can see the full list of changes between each SQLAlchemy-Continuum release.


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
