"""Extended Vaanix API tests covering features not in test_vaanix_api.py:
- /auth/refresh
- users search, profile update, block/unblock/blocked list
- group conversations + admin-only participant management
- mute/unmute, conversations list/get
- image message, pagination, read receipt update
- delete-for-me / delete-for-all
- reactions toggle/replace
- star/unstar + /messages/starred
- /messages/search
- WebSocket /api/ws presence + typing + ping/pong
"""
import json
import time
import uuid
import asyncio
import pytest
import requests
from .conftest import auth_headers, API, BASE_URL


def _email(prefix: str = "EXT") -> str:
    return f"TEST_{prefix}_{uuid.uuid4().hex[:8]}@vaanix.app"


def _login(email: str, name: str = "TEST"):
    r = requests.post(
        f"{API}/auth/dev-login",
        json={"email": email, "display_name": name},
    )
    assert r.status_code == 200, r.text
    d = r.json()
    # dev-login does not issue a refresh-token-as-bearer the same way verify-otp
    # does, but the refresh_token is still in the response payload for parity.
    return d["access_token"], d["refresh_token"], d["user"]


@pytest.fixture(scope="module")
def alice():
    return _login(_email("alice"), "Alice X")


@pytest.fixture(scope="module")
def bob():
    return _login(_email("bob"), "Bob Y")


@pytest.fixture(scope="module")
def carol():
    return _login(_email("carol"), "Carol Z")


# ============================================================
# AUTH refresh
# ============================================================
class TestAuthRefresh:
    def test_refresh_returns_new_access_token(self, alice):
        _, refresh, _ = alice
        r = requests.post(f"{API}/auth/refresh", headers={"Authorization": f"Bearer {refresh}"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "access_token" in body and len(body["access_token"]) > 20

    def test_refresh_with_invalid_token(self):
        r = requests.post(f"{API}/auth/refresh", headers={"Authorization": "Bearer not.a.jwt"})
        assert r.status_code == 401


# ============================================================
# USERS
# ============================================================
class TestUsers:
    def test_profile_update(self, alice):
        tok, _, _ = alice
        r = requests.put(
            f"{API}/users/me",
            headers=auth_headers(tok),
            json={"bio": "extended-bio", "status": "Vibing", "display_name": "Alice X"},
        )
        assert r.status_code == 200, r.text
        u = r.json()
        assert u["bio"] == "extended-bio"
        assert u["status"] == "Vibing"
        # GET back via /auth/me
        me = requests.get(f"{API}/auth/me", headers=auth_headers(tok)).json()
        assert me["bio"] == "extended-bio"

    def test_user_search_with_q(self, alice, bob):
        tok, _, _ = alice
        _, _, b_user = bob
        # Search by part of bob's email
        q = b_user["email"].split("@")[0][:8]
        r = requests.get(f"{API}/users", headers=auth_headers(tok), params={"q": q})
        assert r.status_code == 200
        assert any(u["id"] == b_user["id"] for u in r.json())

    def test_block_unblock_and_blocked_list(self, alice, carol):
        a_tok, _, _ = alice
        _, _, c_user = carol
        # Block
        r = requests.post(f"{API}/users/{c_user['id']}/block", headers=auth_headers(a_tok))
        assert r.status_code == 200
        # Blocked list
        bl = requests.get(f"{API}/users/blocked", headers=auth_headers(a_tok)).json()
        assert any(u["id"] == c_user["id"] for u in bl)
        # /users excludes blocked
        users = requests.get(f"{API}/users", headers=auth_headers(a_tok)).json()
        assert all(u["id"] != c_user["id"] for u in users)
        # Unblock
        r = requests.post(f"{API}/users/{c_user['id']}/unblock", headers=auth_headers(a_tok))
        assert r.status_code == 200
        bl2 = requests.get(f"{API}/users/blocked", headers=auth_headers(a_tok)).json()
        assert all(u["id"] != c_user["id"] for u in bl2)


# ============================================================
# CONVERSATIONS (group + mute + participants)
# ============================================================
@pytest.fixture(scope="module")
def group_conv(alice, bob, carol):
    a_tok, _, a_user = alice
    _, _, b_user = bob
    _, _, c_user = carol
    r = requests.post(
        f"{API}/conversations",
        headers=auth_headers(a_tok),
        json={"type": "group", "name": "TEST_Group", "participant_ids": [b_user["id"]]},
    )
    assert r.status_code == 200, r.text
    return r.json()


class TestConversations:
    def test_create_group_returns_admin(self, group_conv, alice):
        _, _, a_user = alice
        assert group_conv["type"] == "group"
        assert group_conv["name"] == "TEST_Group"
        assert a_user["id"] in group_conv["admins"]
        assert len(group_conv["participants"]) >= 2

    def test_group_without_name_400(self, alice, bob):
        a_tok, _, _ = alice
        _, _, b_user = bob
        r = requests.post(
            f"{API}/conversations",
            headers=auth_headers(a_tok),
            json={"type": "group", "participant_ids": [b_user["id"]]},
        )
        assert r.status_code == 400

    def test_list_and_get_conversation(self, group_conv, alice):
        a_tok, _, _ = alice
        lst = requests.get(f"{API}/conversations", headers=auth_headers(a_tok)).json()
        assert any(c["id"] == group_conv["id"] for c in lst)
        one = requests.get(
            f"{API}/conversations/{group_conv['id']}", headers=auth_headers(a_tok)
        )
        assert one.status_code == 200
        assert one.json()["id"] == group_conv["id"]

    def test_mute_unmute(self, group_conv, alice):
        a_tok, _, _ = alice
        cid = group_conv["id"]
        r = requests.post(f"{API}/conversations/{cid}/mute", headers=auth_headers(a_tok))
        assert r.status_code == 200
        c = requests.get(f"{API}/conversations/{cid}", headers=auth_headers(a_tok)).json()
        assert c["muted"] is True
        r = requests.post(f"{API}/conversations/{cid}/unmute", headers=auth_headers(a_tok))
        assert r.status_code == 200
        c = requests.get(f"{API}/conversations/{cid}", headers=auth_headers(a_tok)).json()
        assert c["muted"] is False

    def test_participant_add_admin_only(self, group_conv, alice, bob, carol):
        a_tok, _, _ = alice
        b_tok, _, _ = bob
        _, _, c_user = carol
        cid = group_conv["id"]
        # Bob (non-admin) tries to add Carol -> 403
        r = requests.post(
            f"{API}/conversations/{cid}/participants/{c_user['id']}",
            headers=auth_headers(b_tok),
        )
        assert r.status_code == 403, r.text
        # Alice (admin) adds Carol -> 200
        r = requests.post(
            f"{API}/conversations/{cid}/participants/{c_user['id']}",
            headers=auth_headers(a_tok),
        )
        assert r.status_code == 200
        assert any(p["id"] == c_user["id"] for p in r.json()["participants"])

    def test_participant_remove_admin_only(self, group_conv, alice, bob, carol):
        a_tok, _, _ = alice
        b_tok, _, _ = bob
        _, _, c_user = carol
        cid = group_conv["id"]
        # Non-admin (bob) trying to remove Carol -> 403
        r = requests.delete(
            f"{API}/conversations/{cid}/participants/{c_user['id']}",
            headers=auth_headers(b_tok),
        )
        assert r.status_code == 403
        # Admin removes Carol -> 200
        r = requests.delete(
            f"{API}/conversations/{cid}/participants/{c_user['id']}",
            headers=auth_headers(a_tok),
        )
        assert r.status_code == 200


# ============================================================
# MESSAGES — image, pagination, delete, react, star, search
# ============================================================
TINY_PNG_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9ZitU8oAAAAASUVORK5CYII="
)


@pytest.fixture(scope="module")
def direct_conv(alice, bob):
    a_tok, _, _ = alice
    _, _, b_user = bob
    r = requests.post(
        f"{API}/conversations",
        headers=auth_headers(a_tok),
        json={"type": "direct", "participant_ids": [b_user["id"]]},
    )
    assert r.status_code == 200
    return r.json()


class TestMessages:
    def test_send_image_message(self, direct_conv, alice):
        a_tok, _, _ = alice
        cid = direct_conv["id"]
        r = requests.post(
            f"{API}/conversations/{cid}/messages",
            headers=auth_headers(a_tok),
            json={"type": "image", "content": TINY_PNG_DATA_URL, "mime_type": "image/png", "file_name": "tiny.png"},
        )
        assert r.status_code == 200, r.text
        m = r.json()
        assert m["type"] == "image"
        assert m["content"].startswith("data:image/png;base64,")

    def test_pagination_with_before_and_limit(self, direct_conv, alice):
        a_tok, _, _ = alice
        cid = direct_conv["id"]
        # send 5 fresh messages
        ids = []
        for i in range(5):
            r = requests.post(
                f"{API}/conversations/{cid}/messages",
                headers=auth_headers(a_tok),
                json={"type": "text", "content": f"TEST_PAG_{i}_{uuid.uuid4().hex[:4]}"},
            )
            assert r.status_code == 200
            ids.append(r.json())
        # limit=2
        r = requests.get(
            f"{API}/conversations/{cid}/messages",
            headers=auth_headers(a_tok),
            params={"limit": 2},
        )
        assert r.status_code == 200
        page1 = r.json()
        assert len(page1) == 2
        # before = oldest of page1
        before = page1[0]["created_at"]
        r = requests.get(
            f"{API}/conversations/{cid}/messages",
            headers=auth_headers(a_tok),
            params={"limit": 2, "before": before},
        )
        assert r.status_code == 200
        page2 = r.json()
        # should not contain page1 ids
        for m in page2:
            assert m["created_at"] < before

    def test_read_receipt_updates_on_list(self, direct_conv, alice, bob):
        a_tok, _, _ = alice
        b_tok, _, b_user = bob
        cid = direct_conv["id"]
        # Alice sends
        text = f"TEST_READ_{uuid.uuid4().hex[:6]}"
        m = requests.post(
            f"{API}/conversations/{cid}/messages",
            headers=auth_headers(a_tok),
            json={"type": "text", "content": text},
        ).json()
        # Bob lists once (this triggers the read-receipt update in the DB)
        requests.get(
            f"{API}/conversations/{cid}/messages",
            headers=auth_headers(b_tok),
        )
        # Bob lists again -> read_by must now include bob (verifies persistence)
        msgs = requests.get(
            f"{API}/conversations/{cid}/messages",
            headers=auth_headers(b_tok),
        ).json()
        target = next((x for x in msgs if x["id"] == m["id"]), None)
        assert target is not None
        assert b_user["id"] in target["read_by"], (
            "Read receipt was not persisted after Bob listed messages "
            "— note: GET /conversations/{id}/messages updates read_by AFTER returning, "
            "so the *first* response will not include the update yet."
        )

    def test_react_toggle_and_replace(self, direct_conv, alice):
        a_tok, _, _ = alice
        cid = direct_conv["id"]
        m = requests.post(
            f"{API}/conversations/{cid}/messages",
            headers=auth_headers(a_tok),
            json={"type": "text", "content": "TEST_REACT"},
        ).json()
        # Add reaction
        r = requests.post(f"{API}/messages/{m['id']}/react", headers=auth_headers(a_tok), json={"emoji": "👍"})
        assert r.status_code == 200
        assert any(rx["emoji"] == "👍" for rx in r.json()["reactions"])
        # Replace with different emoji -> should swap (only 1 reaction per user)
        r = requests.post(f"{API}/messages/{m['id']}/react", headers=auth_headers(a_tok), json={"emoji": "❤️"})
        assert r.status_code == 200
        rxs = r.json()["reactions"]
        assert len(rxs) == 1 and rxs[0]["emoji"] == "❤️"
        # Toggle same emoji -> remove
        r = requests.post(f"{API}/messages/{m['id']}/react", headers=auth_headers(a_tok), json={"emoji": "❤️"})
        assert r.status_code == 200
        assert r.json()["reactions"] == []

    def test_star_unstar_and_starred_list(self, direct_conv, alice):
        a_tok, _, _ = alice
        cid = direct_conv["id"]
        m = requests.post(
            f"{API}/conversations/{cid}/messages",
            headers=auth_headers(a_tok),
            json={"type": "text", "content": "TEST_STAR_xyz"},
        ).json()
        r = requests.post(f"{API}/messages/{m['id']}/star", headers=auth_headers(a_tok))
        assert r.status_code == 200 and r.json()["starred"] is True
        starred = requests.get(f"{API}/messages/starred", headers=auth_headers(a_tok)).json()
        assert any(x["id"] == m["id"] for x in starred)
        # Unstar
        r = requests.post(f"{API}/messages/{m['id']}/star", headers=auth_headers(a_tok))
        assert r.status_code == 200 and r.json()["starred"] is False
        starred2 = requests.get(f"{API}/messages/starred", headers=auth_headers(a_tok)).json()
        assert all(x["id"] != m["id"] for x in starred2)

    def test_delete_for_me_and_for_all(self, direct_conv, alice, bob):
        a_tok, _, _ = alice
        b_tok, _, _ = bob
        cid = direct_conv["id"]
        m1 = requests.post(
            f"{API}/conversations/{cid}/messages",
            headers=auth_headers(a_tok),
            json={"type": "text", "content": "TEST_DEL_ME"},
        ).json()
        m2 = requests.post(
            f"{API}/conversations/{cid}/messages",
            headers=auth_headers(a_tok),
            json={"type": "text", "content": "TEST_DEL_ALL"},
        ).json()
        # delete-for-me by Alice -> hidden from Alice
        r = requests.delete(f"{API}/messages/{m1['id']}", headers=auth_headers(a_tok))
        assert r.status_code == 200
        a_msgs = requests.get(
            f"{API}/conversations/{cid}/messages", headers=auth_headers(a_tok)
        ).json()
        assert all(x["id"] != m1["id"] for x in a_msgs)
        # Bob should still see m1 (only deleted-for-me on alice's side)
        b_msgs = requests.get(
            f"{API}/conversations/{cid}/messages", headers=auth_headers(b_tok)
        ).json()
        assert any(x["id"] == m1["id"] for x in b_msgs)
        # Bob (non-sender) tries delete-for-all -> 403
        r = requests.delete(
            f"{API}/messages/{m2['id']}", headers=auth_headers(b_tok), params={"for_all": "true"}
        )
        assert r.status_code == 403
        # Alice (sender) deletes-for-all
        r = requests.delete(
            f"{API}/messages/{m2['id']}", headers=auth_headers(a_tok), params={"for_all": "true"}
        )
        assert r.status_code == 200
        # Both see content blanked / deleted_for_all=True
        b_msgs2 = requests.get(
            f"{API}/conversations/{cid}/messages", headers=auth_headers(b_tok)
        ).json()
        target = next((x for x in b_msgs2 if x["id"] == m2["id"]), None)
        # depending on implementation it may still appear with deleted_for_all=True or be filtered
        if target is not None:
            assert target.get("deleted_for_all") is True

    def test_search_messages(self, direct_conv, alice):
        a_tok, _, _ = alice
        cid = direct_conv["id"]
        unique = f"SRCHTOKEN{uuid.uuid4().hex[:8]}"
        requests.post(
            f"{API}/conversations/{cid}/messages",
            headers=auth_headers(a_tok),
            json={"type": "text", "content": f"hello {unique} world"},
        )
        r = requests.get(f"{API}/messages/search", headers=auth_headers(a_tok), params={"q": unique})
        assert r.status_code == 200
        assert any(unique in m["content"] for m in r.json())


# ============================================================
# WEBSOCKET
# ============================================================
class TestWebSocket:
    def test_ws_connect_ping_pong_and_typing(self, alice, bob, direct_conv):
        try:
            import websockets  # noqa
        except ImportError:
            pytest.skip("websockets package not installed")

        a_tok, _, _ = alice
        b_tok, _, b_user = bob
        cid = direct_conv["id"]
        ws_base = BASE_URL.replace("https://", "wss://").replace("http://", "ws://")

        async def run():
            import websockets
            uri_a = f"{ws_base}/api/ws?token={a_tok}"
            uri_b = f"{ws_base}/api/ws?token={b_tok}"
            async with websockets.connect(uri_a) as wsa, websockets.connect(uri_b) as wsb:
                # ping/pong
                await wsa.send(json.dumps({"type": "ping"}))
                pong = json.loads(await asyncio.wait_for(wsa.recv(), timeout=5))
                # presence events may interleave — drain until pong
                deadline = time.time() + 5
                while pong.get("type") != "pong" and time.time() < deadline:
                    pong = json.loads(await asyncio.wait_for(wsa.recv(), timeout=5))
                assert pong["type"] == "pong"

                # typing event from alice -> bob should receive
                await wsa.send(json.dumps({"type": "typing", "conversation_id": cid, "is_typing": True}))
                got_typing = False
                deadline = time.time() + 5
                while time.time() < deadline:
                    try:
                        evt = json.loads(await asyncio.wait_for(wsb.recv(), timeout=2))
                    except asyncio.TimeoutError:
                        break
                    if evt.get("type") == "typing" and evt.get("conversation_id") == cid:
                        got_typing = True
                        break
                assert got_typing, "Bob did not receive typing event"

        asyncio.run(run())

    def test_ws_invalid_token_rejected(self):
        try:
            import websockets
        except ImportError:
            pytest.skip("websockets not installed")
        ws_base = BASE_URL.replace("https://", "wss://").replace("http://", "ws://")

        async def run():
            import websockets
            uri = f"{ws_base}/api/ws?token=not.a.valid.jwt"
            with pytest.raises(Exception):
                async with websockets.connect(uri) as ws:
                    await asyncio.wait_for(ws.recv(), timeout=3)

        asyncio.run(run())
