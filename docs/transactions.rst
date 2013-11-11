Transactions
============


TransactionLog
--------------


For each committed transaction SQLAlchemy-Continuum creates a new TransactionLog record.

TransactionLog can be queried just like any other sqlalchemy declarative model.

::


    TransactionLog = Article.__versioned__['transaction_class']

    # find all transactions
    session.query(TransactionLog).all()


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
        .filter(TransactionLog.meta['some_key'] == 'some value')
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



Find entities that changed in given transaction
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can easily get a dictionary of all changed entities by accessing the changed_entities property of
given transaction. This dictionary contains class objects as keys and entities as values.


::


    tx_log = self.session.query(TransactionLog).first()

    tx_log.changed_entities
    # dict of changed entities


Workflow internals
------------------

Consider the following code snippet where we create a new article.

::


    article = Article()
    article.name = u'Some article'
    article.content = u'Some content'
    session.add(article)
    session.commit()



This would execute the following SQL queries (on PostgreSQL)


* INSERT INTO article (name, content) VALUES (?, ?)
    params: ('Some article', 'Some content')
* INSERT INTO transaction_log (issued_at) VALUES (?)
    params: (datetime.utcnow())
* INSERT INTO article_history (id, name, content, transaction_id) VALUES (?, ?, ?, ?)
    params: (article id from query 1, 'Some article', 'Some content', transaction id from query 2)
* INSERT INTO transaction_changes (transaction_id, entity_name) VALUES (?, ?)
    params: (transaction id from query 2, 'article')
