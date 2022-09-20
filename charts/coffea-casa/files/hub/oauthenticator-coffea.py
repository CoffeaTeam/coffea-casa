import os
from kubernetes import client
from oauthenticator.generic import GenericOAuthenticator

class CoffeaOAuthenticator(GenericOAuthenticator):

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

    # Call GenericOAuthenticator to refresh tokens, then and push into k8s secret
    async def refresh_user(self, user, handler=None):
        user_info = await super().refresh_user(user, handler)

        # If it's not a dict, no new info
        if not isinstance(user_info, dict):
            return user_info

        k8s_namespace = os.environ.get('POD_NAMESPACE', 'default')

        # Get the access_token
        try:
            access_token = user_info['auth_state']['access_token']
        except KeyError:
            # No access_token. Bail out.
            return user_info

        secret_name = self.username_to_secretname(user.name)

        # Retrieve the existing secret
        try:
            api = client.CoreV1Api()
            secret = api.read_namespaced_secret(secret_name, k8s_namespace)
        except client.exceptions.ApiException as e:
            # If secret cannot be read, force a re-auth to sort out the state
            self.log.error(
                'Failed to retrieve secret for %s because %s',
                user.name,
                e
            )
            return False

        # Push token into secret
        secret.string_data = { 'access_token': access_token }
        api.patch_namespaced_secret(secret_name, k8s_namespace, secret)

        return user_info
