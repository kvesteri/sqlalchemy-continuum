Plugins
=======


.. automodule:: sqlalchemy_continuum.plugins.flask

.. automodule:: sqlalchemy_continuum.plugins.property_mod_tracker

.. automodule:: sqlalchemy_continuum.plugins.transaction_changes


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
                TransactionLog'some value'
            )
        )
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
