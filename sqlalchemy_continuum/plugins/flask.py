from __future__ import absolute_import

from flask import request
from flask.globals import _app_ctx_stack, _request_ctx_stack
from flask.ext.login import current_user
import sqlalchemy as sa
from .base import Plugin


def fetch_current_user_id():
    # Return None if we are outside of request context.
    if _app_ctx_stack.top is None or _request_ctx_stack.top is None:
        return
    try:
        return current_user.id
    except AttributeError:
        return


def fetch_remote_addr():
    # Return None if we are outside of request context.
    if _app_ctx_stack.top is None or _request_ctx_stack.top is None:
        return
    return request.remote_addr


class FlaskPlugin(Plugin):
    def after_build_tx_class(self, manager):
        Transaction = manager.transaction_log_cls
        Transaction.remote_addr = sa.Column(sa.String(50))

        Transaction.user_id = sa.Column(
            sa.Integer,
            sa.ForeignKey('user.id'),
            index=True
        )
        Transaction.user = sa.orm.relationship('User')

    def before_create_tx_object(self, uow, session):
        uow.current_transaction.user_id = fetch_current_user_id()
        uow.current_transaction.remote_addr = fetch_remote_addr()
