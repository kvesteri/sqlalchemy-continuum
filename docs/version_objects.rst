Version objects
===============


Operation types
---------------

When changing entities and committing results into database Continuum saves the used
operations (INSERT, UPDATE or DELETE) into version entities. The operation types are stored
by default to a small integer field named 'operation_type'. Class called 'Operation' holds
convenient constants for these values as shown below:

::


    from sqlalchemy_continuum import Operation

    article = Article(name=u'Some article')
    session.add(article)
    session.commit()

    article.versions[0].operation_type == Operation.INSERT

    article.name = u'Some updated article'
    session.commit()
    article.versions[1].operation_type == Operation.UPDATE

    session.delete(article)
    session.commit()
    article.versions[2].operation_type == Operation.DELETE


Version traversal
-----------------

::

    first_version = article.versions[0]
    first_version.index
    # 0


    second_version = first_version.next
    assert second_version == article.versions[1]

    second_version.previous == first_version
    # True

    second_version.index
    # 1


Changeset
---------

Continuum provides easy way for getting the changeset of given version object. Each version contains a changeset
property which holds a dict of changed fields in that version.

::


    article = Article(name=u'New article', content=u'Some content')
    session.add(article)
    session.commit(article)

    version = article.versions[0]
    version.changeset
    # {
    #   'id': [None, 1],
    #   'name': [None, u'New article'],
    #   'content': [None, u'Some content']
    # }
    article.name = u'Updated article'
    session.commit()

    version = article.versions[1]
    version.changeset
    # {
    #   'name': [u'New article', u'Updated article'],
    # }

    session.delete(article)
    version = article.versions[1]
    version.changeset
    # {
    #   'id': [1, None]
    #   'name': [u'Updated article', None],
    #   'content': [u'Some content', None]
    # }


SQLAlchemy-Continuum also provides a utility function called changeset. With this function
you can easily check the changeset of given object in current transaction.



::


    from sqlalchemy_continuum import changeset


    article = Article(name=u'Some article')
    changeset(article)
    # {'name': [None, u'Some article']}


Version relationships
---------------------

Each version object reflects all parent object relationships. You can think version object relations as 'relations of parent object in given point in time'.

Lets say you have two models: Article and Category. Each Article has one Category. In the following example we first add article and category objects into database.

Continuum saves new ArticleVersion and CategoryVersion records in the background. After that we update the created article entity to use another category. Continuum creates new version objects accordingly.

Lastly we check the category relations of different article versions.


::


    category = Category(name=u'Some category')
    article = Article(
        name=u'Some article',
        category=category
    )
    session.add(article)
    session.commit()

    article.category = Category(name=u'Some other category')
    session.commit()


    article.versions[0].category.name  # u'Some category'
    article.versions[1].category.name  # u'Some other category'


The logic how SQLAlchemy-Continuum builds these relationships is within the RelationshipBuilder class.


Relationships to non-versioned classes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Let's take previous example of Articles and Categories. Now consider that only Article model is versioned:


::


    class Article(Base):
        __tablename__ = 'article'
        __versioned__ = {}

        id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
        name = sa.Column(sa.Unicode(255), nullable=False)


    class Category(Base):
        __tablename__ = 'tag'

        id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
        name = sa.Column(sa.Unicode(255))
        article_id = sa.Column(sa.Integer, sa.ForeignKey(Article.id))
        article = sa.orm.relationship(
            Article,
            backref=sa.orm.backref('categories')
        )


Here Article versions will still reflect the relationships of Article model but they will simply return Category objects instead of CategoryVersion objects:


::


    category = Category(name=u'Some category')
    article = Article(
        name=u'Some article',
        category=category
    )
    session.add(article)
    session.commit()

    article.category = Category(name=u'Some other category')
    session.commit()

    version = article.versions[0]
    version.category.name                   # u'Some other category'
    isinstance(version.category, Category)  # True


Dynamic relationships
^^^^^^^^^^^^^^^^^^^^^

If the parent class has a dynamic relationship it will be reflected as a property which returns a query in the associated version class.

::

    class Article(Base):
        __tablename__ = 'article'
        __versioned__ = {}

        id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
        name = sa.Column(sa.Unicode(255), nullable=False)


    class Tag(Base):
        __tablename__ = 'tag'
        __versioned__ = {}

        id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
        name = sa.Column(sa.Unicode(255))
        article_id = sa.Column(sa.Integer, sa.ForeignKey(Article.id))
        article = sa.orm.relationship(
            Article,
            backref=sa.orm.backref(
                'tags',
                lazy='dynamic'
            )
        )

    article = Article()
    article.name = u'Some article'
    article.content = u'Some content'
    session.add(article)
    session.commit()

    tag_query = article.versions[0].tags
    tag_query.all()  # return all tags for given version

    tag_query.count()  # return the tag count for given version

