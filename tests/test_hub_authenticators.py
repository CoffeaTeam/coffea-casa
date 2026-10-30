"""Unit tests for the hub authenticators shipped in charts/coffea-casa/files/hub-extra.

These run against the hub's own stack (jupyterhub, oauthenticator,
jupyterhub-multiauthenticator, kubernetes_asyncio), which is not a dependency
of the coffea_casa package, so they are skipped unless it is installed, e.g.:

    pip install jupyterhub==5.5.1 oauthenticator==17.4.0 \
        jupyterhub-multiauthenticator==0.4.0 kubernetes-asyncio pytest
"""
import asyncio
import importlib.util
import pathlib

import pytest

pytest.importorskip("jupyterhub")
pytest.importorskip("oauthenticator")
pytest.importorskip("multiauthenticator")
pytest.importorskip("kubernetes_asyncio")

from jupyterhub.auth import Authenticator  # noqa: E402
from tornado.httpclient import HTTPClientError  # noqa: E402

HUB_EXTRA = (
    pathlib.Path(__file__).resolve().parent.parent
    / "charts" / "coffea-casa" / "files" / "hub-extra"
)


def _load(module_name, filename):
    spec = importlib.util.spec_from_file_location(module_name, HUB_EXTRA / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


coffea_oauth = _load("coffea_oauthenticator", "oauthenticator-coffea.py")
coffea_multi = _load("coffea_multiauthenticator", "multiauthenticator-coffea.py")


class FakeUser:
    name = "user@example.org"

    def __init__(self, auth_state):
        self.auth_state = auth_state

    async def get_auth_state(self):
        return self.auth_state


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# CoffeaOAuthenticator
# ---------------------------------------------------------------------------

@pytest.fixture
def oauth():
    return coffea_oauth.CoffeaOAuthenticator(
        enable_auth_state=True,
        client_id="client",
        client_secret="secret",
        token_url="https://idp.example.org/token",
        userdata_url="https://idp.example.org/userinfo",
    )


def _auth_model(token_info):
    return {
        "name": "user@example.org",
        "auth_state": {
            "access_token": token_info["access_token"],
            "refresh_token": token_info.get("refresh_token"),
        },
    }


def test_refresh_without_auth_state_is_a_noop(oauth):
    assert run(oauth._refresh_tokens(FakeUser(None))) is True


def test_refresh_uses_refresh_token_proactively(oauth, monkeypatch):
    requests = []

    async def get_token_info(handler, params):
        requests.append(params)
        return {"access_token": "new-access"}

    async def token_to_auth_model(token_info):
        return _auth_model(token_info)

    monkeypatch.setattr(oauth, "get_token_info", get_token_info)
    monkeypatch.setattr(oauth, "_token_to_auth_model", token_to_auth_model)

    user = FakeUser({"access_token": "still-valid", "refresh_token": "refresh"})
    model = run(oauth._refresh_tokens(user))

    assert requests[0]["grant_type"] == "refresh_token"
    assert requests[0]["refresh_token"] == "refresh"
    assert model["auth_state"]["access_token"] == "new-access"
    # The provider returned no new refresh_token: the current one is kept
    assert model["auth_state"]["refresh_token"] == "refresh"


@pytest.mark.parametrize("error", [HTTPClientError(400), HTTPClientError(401)])
def test_refresh_rejected_requires_login(oauth, monkeypatch, error):
    async def get_token_info(handler, params):
        raise error

    monkeypatch.setattr(oauth, "get_token_info", get_token_info)
    user = FakeUser({"access_token": "a", "refresh_token": "refresh"})
    assert run(oauth._refresh_tokens(user)) is False


@pytest.mark.parametrize(
    "error", [HTTPClientError(503), HTTPClientError(599), ConnectionRefusedError()]
)
def test_refresh_provider_unavailable_keeps_session(oauth, monkeypatch, error):
    async def get_token_info(handler, params):
        raise error

    monkeypatch.setattr(oauth, "get_token_info", get_token_info)
    user = FakeUser({"access_token": "a", "refresh_token": "refresh"})
    assert run(oauth._refresh_tokens(user)) is True


def test_refresh_without_refresh_token_falls_back_to_upstream(oauth, monkeypatch):
    async def token_to_auth_model(token_info):
        raise HTTPClientError(401)

    async def get_token_info(handler, params):
        raise AssertionError("token endpoint must not be called")

    monkeypatch.setattr(oauth, "_token_to_auth_model", token_to_auth_model)
    monkeypatch.setattr(oauth, "get_token_info", get_token_info)
    user = FakeUser({"access_token": "expired", "token_response": {}})
    # Expired access_token and nothing to refresh it with: upstream says re-login
    assert run(oauth._refresh_tokens(user)) is False


def test_refresh_disabled_uses_upstream(oauth, monkeypatch):
    oauth.always_refresh_tokens = False

    async def token_to_auth_model(token_info):
        return _auth_model(token_info)

    async def get_token_info(handler, params):
        raise AssertionError("token endpoint must not be called")

    monkeypatch.setattr(oauth, "_token_to_auth_model", token_to_auth_model)
    monkeypatch.setattr(oauth, "get_token_info", get_token_info)
    user = FakeUser({
        "access_token": "valid",
        "refresh_token": "refresh",
        "token_response": {"access_token": "valid"},
    })
    model = run(oauth._refresh_tokens(user))
    assert model["auth_state"]["access_token"] == "valid"


@pytest.fixture
def fake_k8s(oauth, monkeypatch):
    """Fake kubernetes_asyncio secret API; returns the {name: string_data} patches"""
    state = {"patched": {}, "read_status": None}

    class FakeSecret:
        string_data = None

    class FakeCoreV1Api:
        def __init__(self, api_client):
            pass

        async def read_namespaced_secret(self, name, namespace):
            if state["read_status"]:
                raise coffea_oauth.client.exceptions.ApiException(
                    status=state["read_status"]
                )
            return FakeSecret()

        async def patch_namespaced_secret(self, name, namespace, secret):
            state["patched"][name] = secret.string_data

    class FakeApiClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    async def refresh_tokens(user, handler=None, **kwargs):
        return {"auth_state": {"access_token": "new-access"}}

    monkeypatch.setattr(oauth, "_refresh_tokens", refresh_tokens)
    monkeypatch.setattr(coffea_oauth.config, "load_incluster_config", lambda: None)
    monkeypatch.setattr(coffea_oauth.client, "ApiClient", FakeApiClient)
    monkeypatch.setattr(coffea_oauth.client, "CoreV1Api", FakeCoreV1Api)
    return state


def test_refresh_user_pushes_access_token_to_secret(oauth, fake_k8s):
    model = run(oauth.refresh_user(FakeUser({})))
    assert model["auth_state"]["access_token"] == "new-access"
    assert fake_k8s["patched"] == {
        "jupyter-user-40example-2eorg": {"access_token": "new-access"}
    }


def test_refresh_user_before_first_spawn(oauth, fake_k8s):
    # refresh_pre_spawn runs before secret_creation_hook has created the secret
    fake_k8s["read_status"] = 404
    model = run(oauth.refresh_user(FakeUser({})))
    assert model["auth_state"]["access_token"] == "new-access"
    assert fake_k8s["patched"] == {}


def test_refresh_user_unreadable_secret_requires_login(oauth, fake_k8s):
    fake_k8s["read_status"] = 403
    assert run(oauth.refresh_user(FakeUser({}))) is False


# ---------------------------------------------------------------------------
# CoffeaMultiAuthenticator
# ---------------------------------------------------------------------------

class RecordingAuthenticator(Authenticator):
    """Subauthenticator stand-in recording which route handled the call"""

    async def authenticate(self, handler, data=None):
        return {"name": "user@example.org", "auth_state": {"access_token": "a"}}

    async def refresh_user(self, user, handler=None, **kwargs):
        return {"auth_state": {"access_token": "refreshed", "by": self.url_scope}}


class StringAuthenticator(Authenticator):
    async def authenticate(self, handler, data=None):
        return "user@example.org"


def _multi(*url_prefixes, authenticator_class=RecordingAuthenticator):
    return coffea_multi.CoffeaMultiAuthenticator(
        username_prefix="",
        authenticators=[
            {"authenticator_class": authenticator_class, "url_prefix": prefix}
            for prefix in url_prefixes
        ],
    )


def test_multi_authenticate_records_route():
    multi = _multi("/cilogon", "/cms")
    cms = multi._authenticators[1]
    model = run(cms.authenticate(None, {}))
    assert model["auth_state"][coffea_multi.URL_SCOPE_KEY] == "/cms"
    assert model["auth_state"]["access_token"] == "a"


def test_multi_authenticate_string_response():
    multi = _multi("/local", authenticator_class=StringAuthenticator)
    model = run(multi._authenticators[0].authenticate(None, {}))
    assert model == {
        "name": "user@example.org",
        "auth_state": {coffea_multi.URL_SCOPE_KEY: "/local"},
    }


def test_multi_refresh_routes_to_login_subauthenticator():
    multi = _multi("/cilogon", "/cms")
    user = FakeUser({"access_token": "a", coffea_multi.URL_SCOPE_KEY: "/cms"})
    model = run(multi.refresh_user(user))
    assert model["auth_state"]["by"] == "/cms"
    # The refreshed auth_state replaces the stored one; the route must survive
    assert model["auth_state"][coffea_multi.URL_SCOPE_KEY] == "/cms"


def test_multi_refresh_without_auth_state_is_a_noop():
    assert run(_multi("/cilogon", "/cms").refresh_user(FakeUser(None))) is True


def test_multi_refresh_unknown_route_requires_login():
    multi = _multi("/cilogon", "/cms")
    assert run(multi.refresh_user(FakeUser({"access_token": "a"}))) is False
    gone = FakeUser({"access_token": "a", coffea_multi.URL_SCOPE_KEY: "/gone"})
    assert run(multi.refresh_user(gone)) is False


def test_multi_refresh_untagged_single_route():
    multi = _multi("/cms")
    model = run(multi.refresh_user(FakeUser({"access_token": "a"})))
    assert model["auth_state"]["by"] == "/cms"


def test_multi_client_secret_from_env(monkeypatch):
    monkeypatch.setenv("HUB_AUTH_CMS_CLIENT_SECRET", "from-env")
    entry = {
        "authenticator_class": "generic-oauth",
        "url_prefix": "/cms",
        "config": {"client_id": "id", "client_secret": "ENV_HUB_AUTH_CMS_CLIENT_SECRET"},
    }
    multi = coffea_multi.CoffeaMultiAuthenticator(
        username_prefix="", authenticators=[entry]
    )
    assert multi._authenticators[0].client_secret == "from-env"
    # The configured value itself is left untouched
    assert entry["config"]["client_secret"] == "ENV_HUB_AUTH_CMS_CLIENT_SECRET"


def test_multi_client_secret_missing_env(monkeypatch):
    monkeypatch.delenv("HUB_AUTH_MISSING", raising=False)
    with pytest.raises(KeyError):
        coffea_multi.CoffeaMultiAuthenticator(
            username_prefix="",
            authenticators=[{
                "authenticator_class": "generic-oauth",
                "url_prefix": "/cms",
                "config": {"client_secret": "ENV_HUB_AUTH_MISSING"},
            }],
        )
