from __future__ import absolute_import

from flask import request
from flask.ext.login import current_user
import sqlalchemy as sa

from ..manager import VersioningManager


class FlaskVersioningManager(VersioningManager):
    def current_user_id(self):
        try:
            return current_user.id
        except AttributeError:
            return

    def remote_addr(self):
        return request.remote_addr

    def transaction_log_base_factory(self, cls):
        tx_log_cls = VersioningManager.transaction_log_base_factory(self, cls)

        class TransactionLogBase(tx_log_cls):
            __abstract__ = True
            remote_addr = sa.Column(sa.String(50))

            @sa.ext.declarative.declared_attr
            def user_id(obj):
                return sa.Column(
                    sa.Integer,
                    sa.ForeignKey('user.id'),
                    default=self.current_user_id,
                    index=True
                )

            @sa.ext.declarative.declared_attr
            def user(obj):
                return sa.orm.relationship('User')

        return TransactionLogBase


versioning_manager = FlaskVersioningManager()
