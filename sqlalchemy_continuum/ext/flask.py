from __future__ import absolute_import

from flask import request
from flask.globals import _app_ctx_stack, _request_ctx_stack
from flask.ext.login import current_user
from ..manager import VersioningManager


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


class FlaskVersioningManager(VersioningManager):
    user = True
    remote_addr = True

    def before_create_transaction(self, values):
        values.setdefault('user_id', fetch_current_user_id())
        values.setdefault('remote_addr', fetch_remote_addr())
        return values

versioning_manager = FlaskVersioningManager()
