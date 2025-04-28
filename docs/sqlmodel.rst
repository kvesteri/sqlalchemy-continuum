SQLModel support
=================

As of version 1.5 SQLAlchemy-Continuum supports models defined via SQLModel library.

Usage
-----

Enabling versions for SQLModel tables is identical to pure SQLAlchemy

1. Call make_versioned() before your models are defined.
2. Add __versioned__ to all models you wish to add versioning to

::

    import sqlmodel
    import sqlalchemy as sa
    from sqlalchemy_continuum import make_versioned


    make_versioned(user_cls=None)


    class Article(sqlmodel.SQLModel, table=True):
        __versioned__ = {}
        __tablename__ = 'article'

        id: int | None = sqlmodel.Field(default=None, primary_key=True)
        name: str = sqlmodel.Field(max_length=255, sa_type=sa.Unicode(255))
        content: str = sqlmodel.Field(sa_type=sa.UnicodeText)


    # after you have defined all your models, call configure_mappers:
    sa.orm.configure_mappers()


Non supported features
----------------------

Following features are not supported with SQLModel

- `base_classes` parameter for `__versioned__` attribute
