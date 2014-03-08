Plugins
=======

Flask
-----

    SQLAlchemy-Continuum comes with built-in extension for Flask. This extensions saves current user id as well as user remote address in transaction log.


::

    from sqlalchemy_continuum.plugins import FlaskPlugin
    from sqlalchemy_continuum import make_versioned


    make_versioned(plugins=[FlaskPlugin])


PropertyModTracker
------------------



TransactionChanges
------------------

In order to be able to to fetch efficiently entities that changed in given transaction SQLAlchemy-Continuum keeps track of changed entities in transaction_changes table.

This table has only two fields: transaction_id and entity_name. If for example transaction consisted of saving 5 new User entities and 1 Article entity, two new rows would be inserted into transaction_changes table.

================    =================
transaction_id          entity_name
----------------    -----------------
233678                  User
233678                  Article
================    =================



TransactionMeta
---------------


Each transaction has a relation to TransactionMeta class. This class contains three columns transaction_id, key and value.

You can easily 'tag' transactions with certain key value pairs by giving these keys and values as parameters to tx_meta function of VersioningManager.


::


    from sqlalchemy_continuum import versioning_manager

    article = Article()
    session.add(article)

    with versioning_manager.tx_meta(some_key=u'some value')
        session.commit()


    # find all transactions with 'article' tags
    query = (
        session.query(TransactionLog)
        .join(TransactionLog.meta)
        .filter(
            db.and_(
                TransactionLog.meta.key == 'some_key',
                TransactionLog'some value')
    )


Using lazy values
^^^^^^^^^^^^^^^^^

::


    from sqlalchemy_continuum import versioning_manager

    article = Article()
    session.add(article)

    with versioning_manager.tx_meta(article_id=lambda: article.id)
        session.commit()


    # find all transactions where meta parameter article_id is given article id
    query = (
        session.query(TransactionLog)
        .filter(TransactionLog.meta['article_id'] == article.id)
    )
