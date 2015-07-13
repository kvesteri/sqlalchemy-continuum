from sqlalchemy_continuum.plugins.base import Plugin
from pyramid.security import authenticated_userid
from pyramid.threadlocal import get_current_request

class PyramidPlugin(Plugin):

    def transaction_args(self, uow, session):
        request = get_current_request()
        user_id = -1
        remote_addr = 'localhost'
        if request:
            user_id = authenticated_userid(request)
            remote_addr = request.remote_addr
        return {
            'user_id': user_id,
            'remote_addr': remote_addr
        }
