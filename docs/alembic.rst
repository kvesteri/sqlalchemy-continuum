Alembic migrations
==================

Each time you make changes to database structure you should also change the associated history tables. When you make changes to your models SQLAlchemy-Continuum automatically alters the history model definitions, hence you can use `alembic revision --autogenerate` just like before. You just need to make sure `make_versioned` function gets called before alembic gathers all your models and `configure_mappers` is called afterwards.

Pay close attention when dropping or moving data from parent tables and reflecting these changes to history tables.

Troubleshooting
###############

If alembic didn't detect any changes or generates reversed migration (tries to remove `*_version` tables from database instead of creating), make sure that `configure_mappers` was called by alembic command.
