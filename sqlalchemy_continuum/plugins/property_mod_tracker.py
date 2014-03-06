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
