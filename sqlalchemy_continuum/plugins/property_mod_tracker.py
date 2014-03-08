"""
The PropertyModTrackerPlugin offers a way of efficiently tracking individual
property modifications. With PropertyModTrackerPlugin you can make efficient
queries such as:

Find all versions of model X where user updated the property A or property B.

Find all versions of model X where user didn't update property A.

PropertyModTrackerPlugin adds separate modified tracking column for each
versioned column. So for example if you have a class Article with versioned
columns `name` and `content`, this plugin would add two additional boolean
columns `name_mod` and `content_mod`. When user commits transactions the
plugin automatically updates these boolean columns.
"""

from copy import copy
import sqlalchemy as sa
from sqlalchemy_utils.functions import has_changes
from .base import Plugin
from ..utils import versioned_column_properties


class PropertyModTrackerPlugin(Plugin):
    column_suffix = '_mod'

    def after_build_history_table_columns(self, table_builder, columns):
        for column in table_builder.parent_table.c:
            if not table_builder.manager.is_excluded_column(
                table_builder.model, column
            ) and not column.primary_key:
                columns.append(
                    sa.Column(
                        column.name + self.column_suffix,
                        sa.Boolean,
                        key=column.key + self.column_suffix,
                        default=False,
                        nullable=False
                    )
                )

    def after_create_history_object(self, uow, parent_obj, history_obj):
        for prop in versioned_column_properties(parent_obj):
            if has_changes(parent_obj, prop.key):
                setattr(
                    history_obj,
                    prop.key + self.column_suffix,
                    True
                )

    def after_construct_changeset(self, history_obj, changeset):
        for key in copy(changeset).keys():
            if key.endswith(self.column_suffix):
                del changeset[key]
