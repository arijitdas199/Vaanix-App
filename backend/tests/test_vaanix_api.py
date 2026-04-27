"""Vaanix backend API tests for OTP-based passwordless auth + chat APIs.

OTP send/verify is delegated to an external service (OTP_BACKEND_URL). Tests
use the dev-only `/api/auth/dev-login` endpoint (gated by DEV_LOGIN_ENABLED=true)
to obtain JWTs without depending on real email delivery.
"""
import uuid
import pytest
import requests
from .conftest import auth_headers, API


def _new_email(prefix: str = "TEST") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}@vaanix.app"


def _request_otp(email: str, display_name: str | None = "TEST User"):
    payload = {"email": email}
    if display_name is not None:
        payload["display_name"] = display_name
    return requests.post(f"{API}/auth/request-otp", json=payload)


def _login(email: str, display_name: str = "TEST User"):
    """Helper: dev-login bypass. Returns (access_token, user)."""
    r = requests.post(
        f"{API}/auth/dev-login",
        json={"email": email, "display_name": display_name},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    return data["access_token"], data["user"]


# ============================================================
# AUTH (OTP)
# ============================================================
class TestAuthOTP:
    def test_root(self):
        r = requests.get(f"{API}/")
        assert r.status_code == 200
        assert r.json().get("app") == "Vaanix"

    def test_request_otp_new_user_dispatches_email(self):
        email = _new_email("TEST_new")
        r = _request_otp(email, "Brand New")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["email_sent"] is True
        assert body["expires_in"] == 300

    def test_request_otp_new_user_without_display_name_returns_400(self):
        email = _new_email("TEST_noname")
        r = _request_otp(email, display_name=None)
        assert r.status_code == 400
        assert "display_name" in r.text.lower()

    def test_verify_otp_wrong_code_returns_401(self):
        # Make sure the user exists by triggering request-otp first
        email = _new_email("TEST_wrong")
        r = _request_otp(email, "Wrong Code")
        assert r.status_code == 200
        v = requests.post(f"{API}/auth/verify-otp", json={"email": email, "otp": "000000"})
        # External service will return invalid OTP since real code wasn't entered
        assert v.status_code in (400, 401), v.text

    def test_dev_login_and_me(self):
        email = _new_email("TEST_dev")
        token, user = _login(email, "Dev User")
        assert token
        assert user["email"] == email.lower()
        assert user["email_verified"] is True
        r = requests.get(f"{API}/auth/me", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["email"] == email.lower()

    def test_me_unauthenticated(self):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code == 401

    @pytest.mark.parametrize("path,payload", [
        ("/auth/login", {"email": "x@y.z", "password": "x"}),
        ("/auth/register", {"email": "x@y.z", "password": "x", "display_name": "x"}),
        ("/auth/forgot-password", {"email": "x@y.z"}),
        ("/auth/reset-password", {"token": "x", "password": "x"}),
    ])
    def test_legacy_endpoints_removed_404(self, path, payload):
        r = requests.post(f"{API}{path}", json=payload)
        assert r.status_code == 404, f"{path} expected 404 got {r.status_code}: {r.text}"


# ============================================================
# CHAT APIS WITH DEV-LOGIN-OBTAINED TOKEN
# ============================================================
@pytest.fixture(scope="module")
def alice():
    token, user = _login(_new_email("TEST_alice"), "Alice Tester")
    return token, user


@pytest.fixture(scope="module")
def bob():
    token, user = _login(_new_email("TEST_bob"), "Bob Tester")
    return token, user


class TestChatFlow:
    def test_create_direct_conversation(self, alice, bob):
        a_tok, _ = alice
        _, b_user = bob
        r = requests.post(
            f"{API}/conversations",
            headers=auth_headers(a_tok),
            json={"type": "direct", "participant_ids": [b_user["id"]]},
        )
        assert r.status_code == 200, r.text
        c = r.json()
        assert c["type"] == "direct"
        assert len(c["participants"]) == 2

    def test_send_and_list_messages(self, alice, bob):
        a_tok, _ = alice
        _, b_user = bob
        conv = requests.post(
            f"{API}/conversations",
            headers=auth_headers(a_tok),
            json={"type": "direct", "participant_ids": [b_user["id"]]},
        ).json()
        text = f"TEST_OTP_HELLO_{uuid.uuid4().hex[:6]}"
        r = requests.post(
            f"{API}/conversations/{conv['id']}/messages",
            headers=auth_headers(a_tok),
            json={"type": "text", "content": text},
        )
        assert r.status_code == 200, r.text
        assert r.json()["content"] == text
        # GET back
        r = requests.get(
            f"{API}/conversations/{conv['id']}/messages",
            headers=auth_headers(a_tok),
        )
        assert r.status_code == 200
        assert any(m["content"] == text for m in r.json())

    def test_users_listing_excludes_self(self, alice):
        a_tok, a_user = alice
        r = requests.get(f"{API}/users", headers=auth_headers(a_tok))
        assert r.status_code == 200
        ids = [u["id"] for u in r.json()]
        assert a_user["id"] not in ids
