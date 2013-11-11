Alembic migrations
==================

Each time you make changes to database structure you should also change the associated history tables. When you make changes to your models SQLAlchemy-Continuum automatically alters the history model definitions, hence you can use `alembic revision --autogenerate` just like before. You just need to make sure `make_versioned` function gets called before alembic gathers all your models.

Pay close attention when dropping or moving data from parent tables and reflecting these changes to history tables.
