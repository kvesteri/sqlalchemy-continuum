Queries
=======


You can query history models just like any other sqlalchemy declarative model.

::

    ArticleHistory = Article.__versioned__['class']

    session.query(ArticleHistory).filter_by(name=u'some name').all()


How many transactions have been executed?
-----------------------------------------

::

    TransactionLog = Article.__versioned__['transaction_class']


    TransactionLog.query.count()


Querying for entities of a class at a given revision
----------------------------------------------------


In the following example we find all articles which were affected by transaction 33.

::

    session.query(ArticleHistory).filter_by(transaction_id=33)



Querying for transactions, at which entities of a given class changed
---------------------------------------------------------------------

In this example we find all transactions which affected any instance of 'Article' model.

::

    TransactionChanges = Article.__versioned__['transaction_changes']


    entries = (
        session.query(TransactionLog)
        .innerjoin(TransactionLog.changes)
        .filter(
            TransactionChanges.entity_name.in(['Article'])
        )
    )



Querying for versions of entity that modified given property
------------------------------------------------------------

In the following example we want to find all versions of Article class which changed the attribute 'name'. This example assumes you have set 'track_property_modifications' configuration option as True.

::

    ArticleHistory = Article.__versioned__['class']

    session.query(ArticleHistory).filter(ArticleHistory.name_mod).all()
