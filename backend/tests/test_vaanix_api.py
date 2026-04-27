"""Vaanix backend API tests for OTP-based passwordless auth + chat APIs.

Note: Resend is in test mode and only delivers to one verified email; for
any other email the backend includes `dev_otp` in the response (DEV_RETURN_OTP=true).
A cooldown of 60s per-email is enforced, so each test uses a unique email.
"""
import time
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
    """Helper: full OTP login. Returns (access_token, user)."""
    r = _request_otp(email, display_name)
    assert r.status_code == 200, r.text
    otp = r.json().get("dev_otp")
    assert otp, f"dev_otp missing: {r.json()}"
    v = requests.post(f"{API}/auth/verify-otp", json={"email": email, "otp": otp})
    assert v.status_code == 200, v.text
    data = v.json()
    return data["access_token"], data["user"]


# ============================================================
# AUTH (OTP)
# ============================================================
class TestAuthOTP:
    def test_root(self):
        r = requests.get(f"{API}/")
        assert r.status_code == 200
        assert r.json().get("app") == "Vaanix"

    def test_request_otp_new_user_returns_dev_otp(self):
        email = _new_email("TEST_new")
        r = _request_otp(email, "Brand New")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert "dev_otp" in body, f"dev_otp must be present in test mode: {body}"
        assert len(body["dev_otp"]) == 6 and body["dev_otp"].isdigit()
        assert body["expires_in"] == 300

    def test_request_otp_new_user_without_display_name_returns_400(self):
        email = _new_email("TEST_noname")
        r = _request_otp(email, display_name=None)
        assert r.status_code == 400
        assert "display_name" in r.text.lower()

    def test_request_otp_cooldown_429(self):
        email = _new_email("TEST_cool")
        r1 = _request_otp(email, "Cool Down")
        assert r1.status_code == 200
        # Immediate second call should be rate limited
        r2 = _request_otp(email, "Cool Down")
        assert r2.status_code == 429, r2.text

    def test_verify_otp_success_and_me(self):
        email = _new_email("TEST_verify")
        token, user = _login(email, "Verify User")
        assert token
        assert user["email"] == email.lower()
        assert user["email_verified"] is True
        # /auth/me with bearer
        r = requests.get(f"{API}/auth/me", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["email"] == email.lower()

    def test_verify_otp_wrong_code_attempts_left_then_invalidated(self):
        email = _new_email("TEST_wrong")
        r = _request_otp(email, "Wrong Code")
        assert r.status_code == 200
        real = r.json()["dev_otp"]
        wrong = "000000" if real != "000000" else "111111"
        # 5 wrong attempts
        for i in range(5):
            v = requests.post(f"{API}/auth/verify-otp", json={"email": email, "otp": wrong})
            assert v.status_code == 401, v.text
            assert "attempts left" in v.text.lower()
        # 6th attempt: OTP invalidated (429) — even if real code provided
        v = requests.post(f"{API}/auth/verify-otp", json={"email": email, "otp": real})
        assert v.status_code in (400, 429), v.text

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

    def test_seeded_users_cleaned_up(self):
        # Indirect check: requesting OTP for these old emails as if NEW — should require display_name.
        # If a doc still exists, server would NOT 400 for missing display_name.
        for email in ["admin@vaanix.app", "aarav@vaanix.app", "meera@vaanix.app"]:
            # ensure unique cooldown bucket by waiting? They are independent emails, no interference.
            r = requests.post(f"{API}/auth/request-otp", json={"email": email})
            assert r.status_code == 400, f"Old seeded user {email} still present: {r.status_code} {r.text}"
            assert "display_name" in r.text.lower()


# ============================================================
# CHAT APIS WITH OTP-OBTAINED TOKEN
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
