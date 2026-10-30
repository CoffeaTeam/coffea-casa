"""
MultiAuthenticator with OAuth token refresh, for hubs offering several login
routes (e.g. CILogon at /hub/cilogon and CMS IAM at /hub/cms).

Upstream jupyterhub-multiauthenticator (0.4.0) does not implement
refresh_user, so under it no subauthenticator ever refreshes its tokens.
This subclass records which login route a user came through in their
auth_state and hands refresh_user to that route's subauthenticator.

Mounted into the hub's site-packages as coffea_multiauthenticator.py;
requires `pip install jupyterhub-multiauthenticator==0.4.0` in the hub.

    c.JupyterHub.authenticator_class = 'coffea_multiauthenticator.CoffeaMultiAuthenticator'

A subauthenticator `client_secret` of the form "ENV_<NAME>" is replaced by
the value of the hub environment variable <NAME>, so secrets can come from
extraEnv/secretKeyRef instead of the (unencrypted) chart values.

Based on John Thiltges' jupyterhub-multiauthenticator branch pr/refresh_user
(github.com/jthiltges/jupyterhub-multiauthenticator, b5094f82, 54581f68) and
his ENV_ client_secret loader for cmsaf-dev (coffea-casa-config 16cbf5b).
"""
import copy
import os

from multiauthenticator import MultiAuthenticator
from traitlets import validate

# auth_state key holding the url_prefix of the route the user logged in with
URL_SCOPE_KEY = 'multiauthenticator_url'
ENV_PREFIX = 'ENV_'


def _tag_url_scope(authenticate, url_scope):
    """Wrap a subauthenticator's authenticate() to record url_scope in auth_state"""
    async def tagged_authenticate(handler, data=None, **kwargs):
        response = await authenticate(handler, data, **kwargs)
        if response is None:
            return None
        if isinstance(response, str):
            # Convert to dict so auth_state can be attached
            response = {'name': response}
        auth_state = response.get('auth_state') or {}
        auth_state[URL_SCOPE_KEY] = url_scope
        response['auth_state'] = auth_state
        return response

    return tagged_authenticate


class CoffeaMultiAuthenticator(MultiAuthenticator):

    @validate('authenticators')
    def _resolve_env_secrets(self, proposal):
        entries = copy.deepcopy(proposal['value'])
        for entry in entries:
            config = entry.get('config', {}) if isinstance(entry, dict) else {}
            secret = config.get('client_secret', '')
            if isinstance(secret, str) and secret.startswith(ENV_PREFIX):
                config['client_secret'] = os.environ[secret[len(ENV_PREFIX):]]
        return entries

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for authenticator in self._authenticators:
            authenticator.authenticate = _tag_url_scope(
                authenticator.authenticate, authenticator.url_scope
            )

    def _subauthenticator_for(self, auth_state):
        url_scope = auth_state.get(URL_SCOPE_KEY)
        for authenticator in self._authenticators:
            if authenticator.url_scope == url_scope:
                return authenticator
        # Logins from before this class was deployed carry no route; with a
        # single route there is no ambiguity.
        if url_scope is None and len(self._authenticators) == 1:
            return self._authenticators[0]
        return None

    async def refresh_user(self, user, handler=None, **kwargs):
        auth_state = await user.get_auth_state()

        # No OAuth auth_state (e.g. admin-created service users, or auth_state
        # disabled): nothing to refresh
        if not auth_state:
            return True

        authenticator = self._subauthenticator_for(auth_state)
        if authenticator is None:
            self.log.info(
                'No login route recorded for %s, need full authentication',
                user.name
            )
            return False

        auth_model = await authenticator.refresh_user(user, handler, **kwargs)

        # A refreshed auth_state replaces the stored one: keep the route
        if isinstance(auth_model, dict) and auth_model.get('auth_state') is not None:
            auth_model['auth_state'][URL_SCOPE_KEY] = authenticator.url_scope
        return auth_model
