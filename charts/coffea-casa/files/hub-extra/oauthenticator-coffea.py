import os

from kubernetes_asyncio import client, config
from oauthenticator.generic import GenericOAuthenticator
from tornado.httpclient import HTTPClientError
from traitlets import Bool


class CoffeaOAuthenticator(GenericOAuthenticator):

    always_refresh_tokens = Bool(
        True,
        config=True,
        help="""
        Exchange the refresh_token for a new access_token on every refresh_user
        call (every Authenticator.auth_refresh_age seconds), instead of only
        once the provider has rejected the current access_token. Keeps the
        access_token pushed into the user's secret valid for data access.
        """,
    )

    # FIXME: Merge with identical function in secret_creation_hook
    @staticmethod
    def escape_username(input_name):
        result = ''
        for character in input_name:
            if character.isalnum():
                result += character
            else:
                result += '-%0x' % ord(character)
        return result

    def username_to_secretname(self, username):
        return 'jupyter-%s' % self.escape_username(username)

    # Proactive refresh from John Thiltges' oauthenticator branch pr/should_refresh
    # (github.com/jthiltges/jupyterhub-oauthenticator, 59994858); structure
    # adapted from oauthenticator 17.4 OAuthenticator.refresh_user (BSD-3-Clause).
    async def _refresh_tokens(self, user, handler=None, **kwargs):
        if not self.enable_auth_state:
            return True

        auth_state = await user.get_auth_state()

        # If no auth_state (e.g. admin-created service user), nothing to refresh
        if not auth_state:
            return True

        refresh_token = auth_state.get('refresh_token', None)

        # Upstream refresh: re-validate the access_token, use the
        # refresh_token only once that fails
        if not (self.always_refresh_tokens and refresh_token) or self.refresh_user_hook:
            return await super().refresh_user(user, handler, **kwargs)

        params = self.build_refresh_token_request_params(refresh_token)
        try:
            token_info = await self.get_token_info(handler, params)
        except (HTTPClientError, OSError) as e:
            code = getattr(e, 'code', None)
            if code is None or code >= 500:
                # Provider unreachable or failing: keep the current tokens
                # and try again on the next refresh
                self.log.warning(
                    'Could not reach token endpoint to refresh %s: %s',
                    user.name,
                    e
                )
                return True
            self.log.info(
                'Error using refresh_token for %s: %s. Requiring fresh login.',
                user.name,
                e
            )
            return False
        except Exception as e:
            self.log.info(
                'Error using refresh_token for %s: %s. Requiring fresh login.',
                user.name,
                e
            )
            return False

        # Providers may not return a new refresh_token; keep the current one
        if not token_info.get('refresh_token'):
            token_info['refresh_token'] = refresh_token

        try:
            auth_model = await self._token_to_auth_model(token_info)
        except Exception as e:
            self.log.error(
                'Error refreshing auth with fresh access_token for %s: %s. Requiring fresh login.',
                user.name,
                e
            )
            return False

        self.log.info('Refreshed oauth tokens for %s', user.name)
        return auth_model

    # Refresh tokens, then push the access_token into the user's k8s secret.
    # The z2jh 4.x hub image ships kubernetes_asyncio (used by KubeSpawner),
    # not the sync `kubernetes` client, so API calls are awaited here.
    async def refresh_user(self, user, handler=None, **kwargs):
        user_info = await self._refresh_tokens(user, handler, **kwargs)

        # If it's not a dict, no new info
        if not isinstance(user_info, dict):
            return user_info

        k8s_namespace = os.environ.get('POD_NAMESPACE', 'default')

        # Get the access_token
        try:
            access_token = user_info['auth_state']['access_token']
        except (KeyError, TypeError):
            # No access_token. Bail out.
            return user_info

        secret_name = self.username_to_secretname(user.name)

        config.load_incluster_config()
        async with client.ApiClient() as api_client:
            api = client.CoreV1Api(api_client)

            # Retrieve the existing secret
            try:
                secret = await api.read_namespaced_secret(secret_name, k8s_namespace)
            except client.exceptions.ApiException as e:
                if e.status == 404:
                    # Not spawned yet (e.g. refresh_pre_spawn on first spawn):
                    # secret_creation_hook creates the secret with this token
                    return user_info
                # If secret cannot be read, force a re-auth to sort out the state
                self.log.error(
                    'Failed to retrieve secret for %s because %s',
                    user.name,
                    e
                )
                return False

            # Push token into secret
            secret.string_data = {'access_token': access_token}
            await api.patch_namespaced_secret(secret_name, k8s_namespace, secret)

        return user_info
