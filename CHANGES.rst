Changelog
---------

Here you can see the full list of changes between each SQLAlchemy-Continuum release.


1.3.3 (2017-11-05)
^^^^^^^^^^^^^^^^^^

- Fixed changeset when updating object in same transaction as inserting it (#141, courtesy of oinopion)


1.3.2 (2017-10-12)
^^^^^^^^^^^^^^^^^^

- Fixed multiple schema handling (#132, courtesy of vault)


1.3.1 (2017-06-28)
^^^^^^^^^^^^^^^^^^

- Fixed subclass retrieval for closest_matching_table (#163, courtesy of debonzi)


1.3.0 (2017-01-30)
^^^^^^^^^^^^^^^^^^

- Dropped py2.6 support
- Fixed memory leaks with UnitOfWork instances (#131, courtesy of quantus)


1.2.4 (2016-01-10)
^^^^^^^^^^^^^^^^^^

- Added explicit sequence names for Oracle (#118, courtesy of apfeiffer1)


1.2.3 (2016-01-10)
^^^^^^^^^^^^^^^^^^

- Added use_module_name configuration option (#119, courtesy of kyheo)


1.2.2 (2015-12-08)
^^^^^^^^^^^^^^^^^^

- Fixed some relationship changes not counted as modifications (#116, courtesy of tvuotila)


1.2.1 (2015-09-27)
^^^^^^^^^^^^^^^^^^

- Fixed deep joined table inheritance handling (#105, courtesy of piotr-dobrogost)
- Fixed naive assumption of related User model always having id column (#107, courtesy of avilaton)
- Fixed one-to-many relationship reverting (#102, courtesy of sdorazio)


1.2.0 (2015-07-31)
^^^^^^^^^^^^^^^^^^

- Removed generated changes attribute from version classes. This attribute can be accessed through `transaction.changes`
- Removed is_modified checking from insert operations


1.1.5 (2014-12-28)
^^^^^^^^^^^^^^^^^^

- Added smart primary key type inspection for user class (#86, courtesy of mattupstate)
- Added support for self-referential version relationship reflection (#88, courtesy of dtheodor)


1.1.4 (2014-12-06)
^^^^^^^^^^^^^^^^^^

- Fixed One-To-Many version relationship handling (#82, courtesy of dtheodor)
- Fixed Many-To-Many version relationship handling (#83, courtesy of dtheodor)
- Fixed inclusion and exclusion of aliased columns
- Removed automatic exclusion of auto-assigned datetime columns and tsvector columns (explicit is better than implicit)


1.1.3 (2014-10-23)
^^^^^^^^^^^^^^^^^^

- Made FlaskPlugin accepts overriding of current_user_id_factory and remote_addr_factory


1.1.2 (2014-10-07)
^^^^^^^^^^^^^^^^^^

- Fixed identifier quoting in trigger syncing


1.1.1 (2014-10-07)
^^^^^^^^^^^^^^^^^^

- Fixed native versioning trigger syncing


1.1.0 (2014-10-02)
^^^^^^^^^^^^^^^^^^

- Added Python 3.4 to test suite
- Added optional native trigger based versioning for PostgreSQL dialect
- Added create_models option
- Added count_versions utility function
- Fixed custom transaction column name handling with models using joined table inheritance
- Fixed subquery strategy support for models using joined table inheritance
- Fixed savepoint handling
- Fixed version model building when no versioned models were found (previously threw AttributeError)
- Replaced plugin template methods before_create_tx_object and after_create_tx_object with transaction_args to better cope with native versioning


1.0.3 (2014-07-16)
^^^^^^^^^^^^^^^^^^

- Added __repr__ for Operations class
- Fixed an issue where assigning unmodified object's attributes in user defined before flush listener would raise TypeError in UnitOfWork


1.0.2 (2014-07-11)
^^^^^^^^^^^^^^^^^^

- Allowed easier overriding of PropertyModTracker column creation
- Rewrote join table inheritance handling schematics (now working with SA 0.9.6)
- SQLAlchemy-Utils dependency updated to 0.26.5


1.0.1 (2014-06-18)
^^^^^^^^^^^^^^^^^^

- Fixed an issue where deleting an object with deferred columns would throw ObjectDeletedError.
- Made viewonly relationships with association tables not register the association table to versioning manager registry.


1.0 (2014-06-16)
^^^^^^^^^^^^^^^^

- Added __repr__ for Transaction class, issue #59
- Made transaction_cls of VersioningManager configurable.
- Removed generic relationships from transaction class to versioned classes.
- Removed generic relationships from transaction changes class to versioned classes.
- Removed relation_naming_function (no longer needed)
- Moved get_bind to SQLAlchemy-Utils
- Removed inflection package from dependencies (no longer needed)
- SQLAlchemy-Utils dependency updated to 0.26.2


1.0b5 (2014-05-07)
^^^^^^^^^^^^^^^^^^

- Added order_by mapper arg ignoring for version class reflection if other than string argument is used
- Added support for customizing the User class which the Transaction class should have relationship to (issue #53)
- Changed get_versioning_manager to throw ClassNotVersioned exception if first argument is not a versioned class
- Fixed relationship reflection from versioned classes to non versioned classes (issue #52)
- SQLAlchemy-Utils dependency updated to 0.25.4


1.0-b4 (2014-04-20)
^^^^^^^^^^^^^^^^^^^

- Fixed many-to-many unit of work inspection when using engine bind instead of collection bind
- Fixed various issues if primary key aliases were used in declarative models
- Fixed an issue where association versioning would not work with custom transaction column name
- SQLAlchemy-Utils dependency updated to 0.25.3


1.0-b3 (2014-04-19)
^^^^^^^^^^^^^^^^^^^

- Added support for concrete inheritance
- Added order_by mapper arg reflection to version classes
- Added support for column_prefix mapper arg
- Made model builder copy inheritance mapper args to version classes from parent classes
- Fixed end transaction id setting for join table inheritance classes. Now end transaction id is set explicitly to all tables in inheritance hierarchy.
- Fixed single table inheritance handling


1.0-b2 (2014-04-09)
^^^^^^^^^^^^^^^^^^^

- Added some schema tools to help migrating between different plugins and versioning strategies
- Added remove_versioning utility function, see issue #45
- Added order_by transaction_id default to versions relationship
- Fixed PropertyModTrackerPlugin association table handling.
- Fixed get_bind schematics (Flask-SQLAlchemy integration wasn't working)
- Fixed a bug where committing a session without objects would result in KeyError
- SQLAlchemy dependency updated to 0.9.4


1.0-b1 (2014-03-14)
^^^^^^^^^^^^^^^^^^^

- Added new plugin architecture
- Added ActivityPlugin
- Naming conventions change: History -> Version (to be consistent throughout Continuum)
- Naming convention change: TransactionLog -> Transaction
- Rewritten reflected relationship model for version classes. Only dynamic relationships are now reflected as dynamic relationships. Other relationships return either lists or scalars.
- One-To-One relationship support for reflected version class relationships
- Removed tx_context context manager. Transaction objects can now be created manually and user has direct access to the parameters of this object.
- Removed tx_meta context manager. Transaction meta objects can now be created explicitly.
- Fixed association reverting when the relationship uses uselist=False
- Fixed one-to-many directed relationship reverting when the relationship uses uselist=False
- Fixed many-to-many relationship handling when multiple links were created during the same transaction
- Added indexes to operation_type, transaction_id and end_transaction_id columns of version classes
- Deprecated extensions
- SQLAlchemy-Utils dependency updated to 0.25.0


0.10.3 (2014-02-27)
^^^^^^^^^^^^^^^^^^^

- Fixed version next / previous handling
- SQLAlchemy dependency updated to 0.9.3
- Fixed column onupdate to history table reflection (issue #47)


0.10.2 (2014-02-10)
^^^^^^^^^^^^^^^^^^^

- Fixed MySQL support (issue #36)
- Added SQLite and MySQL to testing matrix


0.10.1 (2013-10-18)
^^^^^^^^^^^^^^^^^^^

- Added vacuum function


0.10.0 (2013-10-09)
^^^^^^^^^^^^^^^^^^^

- Validity versioning strategy
- Changeset supports custom transaction column names
- Reify -> Revert
- Fixed revert to support class level column exclusion


0.9.0 (2013-09-12)
^^^^^^^^^^^^^^^^^^

- Ability to track property modifications
- New configuration options: track_property_modifications and modified_flag_suffix


0.8.7 (2013-09-04)
^^^^^^^^^^^^^^^^^^

- Only autoincremented columns marked as autoincrement=False for history tables. This enables alembic migrations to generate without annoying explicit autoincrement=False args.


0.8.6 (2013-08-21)
^^^^^^^^^^^^^^^^^^

- Custom database schema support added


0.8.5 (2013-08-01)
^^^^^^^^^^^^^^^^^^

- TSVectorType columns not versioned by default (in order to avoid massive version histories)


0.8.4 (2013-07-31)
^^^^^^^^^^^^^^^^^^

- Full MySQL and SQLite support added


0.8.3 (2013-07-29)
^^^^^^^^^^^^^^^^^^

- Fixed UnitOfWork changed entities handling (now checks only for versioned attributes not all object attributes)
- Fixed UnitOfWork TransactionMeta object creation (now checks if actual modifications were made)


0.8.2 (2013-07-26)
^^^^^^^^^^^^^^^^^^^

- Fixed MySQL history table primary key generation (autoincrement=False now forced for transaction_id column)


0.8.1 (2013-07-25)
^^^^^^^^^^^^^^^^^^^

- Added support for SQLAlchemy-i18n


0.8.0 (2013-07-25)
^^^^^^^^^^^^^^^^^^^

- Added database independent transaction meta parameter handling (formerly supported postgres only)


0.7.13 (2013-07-24)
^^^^^^^^^^^^^^^^^^^

- Smarter is_modified handling for UnitOfWork (now understands excluded properties)


0.7.12 (2013-07-23)
^^^^^^^^^^^^^^^^^^^

- Fixed FlaskVersioningManager schematics when working outside of request context (again)
- Added possibility to use custom UnitOfWork class


0.7.11 (2013-07-23)
^^^^^^^^^^^^^^^^^^^

- Fixed FlaskVersioningManager schematics when working outside of request context


0.7.10 (2013-07-23)
^^^^^^^^^^^^^^^^^^^

- Fixed is_auto_assigned_date_column (again)
- Moved some core utility functions to SQLAlchemy-Utils


0.7.9 (2013-07-23)
^^^^^^^^^^^^^^^^^^

- Fixed is_auto_assigned_date_column
- Inflection added to requirements


0.7.8 (2013-07-03)
^^^^^^^^^^^^^^^^^^

- Removed Versioned base class (adding __versioned__ attribute and calling make_versioned() is sufficient for making declarative class versioned)


0.7.7 (2013-07-03)
^^^^^^^^^^^^^^^^^^

- DateTime columns with defaults excluded by default from history classes
- Column inclusion added as option


0.7.6 (2013-07-03)
^^^^^^^^^^^^^^^^^^

- Smarter changeset handling


0.7.5 (2013-07-03)
^^^^^^^^^^^^^^^^^^

- Improved reify() speed


0.7.4 (2013-07-03)
^^^^^^^^^^^^^^^^^^

- Fixed changeset when parent contains more columns than version class.


0.7.3 (2013-06-27)
^^^^^^^^^^^^^^^^^^

- Transaction log and transaction changes records only created if actual net changes were made during transaction.


0.7.2 (2013-06-27)
^^^^^^^^^^^^^^^^^^

- Removed last references for old revision versioning


0.7.1 (2013-06-27)
^^^^^^^^^^^^^^^^^^

- Added is_versioned utility function
- Fixed before operation listeners


0.7.0 (2013-06-27)
^^^^^^^^^^^^^^^^^^

- Version tables no longer have revision column
- Parent tables no longer need revision column
- Version tables primary key is now (parent table pks + transaction_id)


0.6.8 (2013-06-26)
^^^^^^^^^^^^^^^^^^

- Make versioned join table inherited classes support multiple consecutive flushes per transaction


0.6.7 (2013-06-26)
^^^^^^^^^^^^^^^^^^

- Fixed association versioning when using executemany


0.6.6 (2013-06-26)
^^^^^^^^^^^^^^^^^^

- Improved transaction log changed_entities schematics


0.6.5 (2013-06-26)
^^^^^^^^^^^^^^^^^^

- Added possibility to add lazy values in transaction context meta


0.6.4 (2013-06-25)
^^^^^^^^^^^^^^^^^^

- Version tables no longer generated when versioning attribute of model set to False


0.6.3 (2013-06-25)
^^^^^^^^^^^^^^^^^^

- Revision column not nullable in version classes


0.6.2 (2013-06-25)
^^^^^^^^^^^^^^^^^^

- Fixed relationship building for non-versioned classes


0.6.1 (2013-06-25)
^^^^^^^^^^^^^^^^^^

- Parent table primary keys remain not nullable in generated version table


0.6.0 (2013-06-25)
^^^^^^^^^^^^^^^^^^

- Added database agnostic versioning (no need for PostgreSQL specific triggers anymore)
- Fixed version object relationships (never worked properly in previous versions)
- New configuration option versioning allows setting the versioning on and off per child class.
- Added column exclusion


0.5.1 (2013-06-20)
^^^^^^^^^^^^^^^^^^

- Added improved context managing capabilities for transactions via VersioningManager.tx_context


0.5.0 (2013-06-20)
^^^^^^^^^^^^^^^^^^

- Removed Versioned base class, versioned objects only need to have __versioned__ defined.
- Session versioning now part of make_versioned function
- Added meta parameter in TransactionLog
- TransactionChanges model for tracking changed entities in given transaction
- Added Flask extension


0.4.2 (2013-06-18)
^^^^^^^^^^^^^^^^^^

- Alembic trigger syncing fixed for drop column and add column


0.4.1 (2013-06-18)
^^^^^^^^^^^^^^^^^^

- Alembic trigger syncing fixed


0.4.0 (2013-06-18)
^^^^^^^^^^^^^^^^^^

- Added support for multiple updates for same row within single transaction
- History tables have now own revision column


0.3.12 (2013-06-18)
^^^^^^^^^^^^^^^^^^^

- Not null constraints removed from all reflected columns
- Fixed reify when parent has not null constraints
- Added support for reifying deletion


0.3.11 (2013-06-18)
^^^^^^^^^^^^^^^^^^^

- Single table inheritance support added


0.3.10 (2013-06-18)
^^^^^^^^^^^^^^^^^^^

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
