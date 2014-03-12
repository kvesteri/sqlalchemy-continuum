Transactions
============


Transaction
-----------


For each committed transaction SQLAlchemy-Continuum creates a new Transaction record.

Transaction can be queried just like any other sqlalchemy declarative model.

::


    Transaction = Article.__versioned__['transaction_class']

    # find all transactions
    session.query(Transaction).all()



Find entities that changed in given transaction
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can easily get a dictionary of all changed entities by accessing the changed_entities property of
given transaction. This dictionary contains class objects as keys and entities as values.


::


    tx_log = self.session.query(Transaction).first()

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
