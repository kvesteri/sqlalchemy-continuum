Configuration
=============

Global and class level configuration
------------------------------------

All Continuum configuration parameters can be set on global level (manager level) and on class level. Setting an option at manager level affects all classes within the scope of the manager's class instrumentation listener (by default all SQLAlchemy declarative models).

In the following example we set 'transaction_column_name' configuration option to False at the manager level.

::


    make_versioned(options={'transaction_column_name': 'my_tx_id'})



As the name suggests class level configuration only applies to given class. Class level configuration can be passed to __versioned__ class attribute.


::


    class User(Base):
        __versioned__ = {
            'transaction_column_name': 'tx_id'
        }


Versioning strategies
---------------------


Similar to Hibernate Envers SQLAlchemy-Continuum offers two distinct versioning strategies 'validity' and 'subquery'. The default strategy is 'validity'.


Validity
^^^^^^^^

The 'validity' strategy saves two columns in each history table, namely 'transaction_id' and 'end_transaction_id'. The names of these columns can be configured with configuration options `transaction_column_name` and `end_transaction_column_name`.

As with 'subquery' strategy for each inserted, updated and deleted entity Continuum creates new version in the history table. However it also updates the end_transaction_id of the previous version to point at the current version. This creates a little bit of overhead during data manipulation.

With 'validity' strategy version traversal is very fast. When accessing previous version Continuum tries to find the version record where the primary keys match and end_transaction_id is the same as the transaction_id of the given version record. When accessing the next version Continuum tries to find the version record where the primary keys match and transaction_id is the same as the end_transaction_id of the given version record.


Pros:
    * Version traversal is much faster since no correlated subqueries are needed


Cons:
    * Updates, inserts and deletes are little bit slower


Subquery
^^^^^^^^

The 'subquery' strategy uses one column in each history table, namely 'transaction_id'. The name of this column can be configured with configuration option `transaction_column_name`.

After each inserted, updated and deleted entity Continuum creates new version in the history table and sets the 'transaction_id' column to point at the current transaction.

With 'subquery' strategy the version traversal is slow. When accessing previous and next versions of given version object needs correlated subqueries.


Pros:
    * Updates, inserts and deletes little bit faster than in 'validity' strategy

Cons:
    * Version traversel much slower



Column exclusion and inclusion
------------------------------

With `exclude` configuration option you can define which entity attributes you want to get versioned. By default Continuum versions all entity attributes.

::


    class User(Base):
        __versioned__ = {
            'exclude': ['picture']
        }

        id = sa.Column(sa.Integer, primary_key=True)
        name = sa.Column(sa.Unicode(255))
        picture = sa.Column(sa.LargeBinary)




Basic configuration options
---------------------------

Here is a full list of configuration options:

* base_classes (default: None)
    A tuple defining history class base classes.

* table_name (default: '%s_version')
    The name of the history table.

* transaction_column_name (default: 'transaction_id')
    The name of the transaction column (used by history tables).

* end_transaction_column_name (default: 'end_transaction_id')
    The name of the end transaction column in history table when using the validity versioning strategy.

* operation_type_column_name (default: 'operation_type')
    The name of the operation type column (used by history tables).

* strategy (default: 'validity')
    The versioning strategy to use. Either 'validity' or 'subquery'


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


Customizing transaction user class
----------------------------------

By default Continuum tries to build a relationship between 'User' class and Transaction class. If you have differently named user class you can simply pass its name to make_versioned:


::


    make_versioned(user_cls='MyUserClass')



If you don't want transactions to contain any user references you can also disable this feature.


::

    make_versioned(user_cls=None)


Customizing versioned mappers
-----------------------------

By default SQLAlchemy-Continuum versions all mappers. You can override this behaviour by passing the desired mapper class/object to make_versioned function.


::

    make_versioned(mapper=my_mapper)


Customizing versioned sessions
------------------------------


By default SQLAlchemy-Continuum versions all sessions. You can override this behaviour by passing the desired session class/object to make_versioned function.


::

    make_versioned(session=my_session)
