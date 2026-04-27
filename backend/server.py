from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import uuid
import json
import asyncio
import logging
import httpx
import jwt
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Set

from fastapi import (
    FastAPI,
    APIRouter,
    HTTPException,
    Request,
    Response,
    Depends,
    WebSocket,
    WebSocketDisconnect,
    Query,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from motor.motor_asyncio import AsyncIOMotorClient

# --------------------------------------------------------------
# Config
# --------------------------------------------------------------
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MIN = 60 * 24 * 7  # 7 days for mobile convenience
REFRESH_TOKEN_DAYS = 30

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

# External OTP microservice (handles email send + OTP verify + 5-min TTL)
OTP_BACKEND_URL = os.environ.get("OTP_BACKEND_URL", "https://otp-backend-lpv2.onrender.com").rstrip("/")
APP_NAME = os.environ.get("APP_NAME", "Vaanix")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("vaanix")

app = FastAPI(title="Vaanix API")
api = APIRouter(prefix="/api")


# --------------------------------------------------------------
# Helpers
# --------------------------------------------------------------
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().isoformat()


def gen_otp() -> str:
    # OTP generation is delegated to the external OTP service.
    return ""


async def send_otp_via_external_service(email: str) -> tuple[bool, Optional[str]]:
    """Calls the external OTP backend to generate + email an OTP.

    Returns (ok, error_message). The external service stores the code in-memory
    with a 5-minute TTL and verifies via /api/auth/verify-otp.
    """
    url = f"{OTP_BACKEND_URL}/api/auth/request-otp"
    try:
        async with httpx.AsyncClient(timeout=30.0) as cli:
            r = await cli.post(url, json={"email": email})
        if r.status_code == 200:
            return True, None
        try:
            err = r.json().get("error") or r.text
        except Exception:
            err = r.text
        logger.error(f"OTP service request-otp failed [{r.status_code}] for {email}: {err}")
        return False, err
    except Exception as e:
        logger.error(f"OTP service request-otp error for {email}: {e}")
        return False, "Email service unavailable. Please try again."


async def verify_otp_via_external_service(email: str, otp: str) -> tuple[bool, Optional[str]]:
    url = f"{OTP_BACKEND_URL}/api/auth/verify-otp"
    try:
        async with httpx.AsyncClient(timeout=15.0) as cli:
            r = await cli.post(url, json={"email": email, "otp": otp})
        if r.status_code == 200:
            return True, None
        try:
            err = r.json().get("error") or r.text
        except Exception:
            err = r.text
        return False, err or "Verification failed"
    except Exception as e:
        logger.error(f"OTP service verify-otp error for {email}: {e}")
        return False, "Verification service unavailable. Please try again."


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": now_utc() + timedelta(minutes=ACCESS_TOKEN_MIN),
        "type": "access",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": now_utc() + timedelta(days=REFRESH_TOKEN_DAYS),
        "type": "refresh",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def public_user(u: Dict[str, Any]) -> Dict[str, Any]:
    if not u:
        return {}
    return {
        "id": u["id"],
        "email": u["email"],
        "display_name": u.get("display_name", ""),
        "avatar": u.get("avatar"),
        "bio": u.get("bio", ""),
        "status": u.get("status", "Hey there! I'm using Vaanix."),
        "online": bool(u.get("online", False)),
        "last_seen": u.get("last_seen"),
        "email_verified": bool(u.get("email_verified", False)),
        "created_at": u.get("created_at"),
    }


async def get_current_user(request: Request) -> Dict[str, Any]:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def set_auth_cookies(response: Response, access: str, refresh: str):
    response.set_cookie("access_token", access, httponly=True, secure=False, samesite="lax",
                        max_age=ACCESS_TOKEN_MIN * 60, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True, secure=False, samesite="lax",
                        max_age=REFRESH_TOKEN_DAYS * 86400, path="/")


# --------------------------------------------------------------
# Pydantic schemas
# --------------------------------------------------------------
class RequestOTPIn(BaseModel):
    email: EmailStr
    display_name: Optional[str] = None  # required if user is new


class VerifyOTPIn(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6)


class ProfileIn(BaseModel):
    display_name: Optional[str] = None
    bio: Optional[str] = None
    status: Optional[str] = None
    avatar: Optional[str] = None  # base64


class CreateConvIn(BaseModel):
    type: str = Field(pattern="^(direct|group)$")
    participant_ids: List[str]
    name: Optional[str] = None
    avatar: Optional[str] = None


class SendMessageIn(BaseModel):
    type: str = Field(pattern="^(text|image|video|document|voice)$")
    content: str  # text or base64 (data url)
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    duration: Optional[float] = None
    reply_to: Optional[str] = None


class ReactIn(BaseModel):
    emoji: str


# --------------------------------------------------------------
# Auth Endpoints (Email + OTP, passwordless)
# --------------------------------------------------------------
@api.post("/auth/request-otp")
async def request_otp(body: RequestOTPIn):
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email})

    if not user:
        if not body.display_name or not body.display_name.strip():
            raise HTTPException(400, "display_name is required for new users")
        user = {
            "id": str(uuid.uuid4()),
            "email": email,
            "display_name": body.display_name.strip(),
            "avatar": None,
            "bio": "",
            "status": "Hey there! I'm using Vaanix.",
            "online": False,
            "last_seen": now_iso(),
            "email_verified": False,
            "blocked_users": [],
            "starred_messages": [],
            "muted_conversations": [],
            "role": "user",
            "created_at": now_iso(),
        }
        await db.users.insert_one(user)

    ok, err = await send_otp_via_external_service(email)
    if not ok:
        raise HTTPException(502, err or "Could not send verification code. Please try again.")

    logger.info(f"[OTP] external service dispatched code to {email}")

    return {
        "ok": True,
        "message": "Verification code sent to your email.",
        "expires_in": 5 * 60,  # external service uses 5-minute TTL
        "is_new_user": user.get("email_verified") is False,
        "email_sent": True,
    }


@api.post("/auth/verify-otp")
async def verify_otp(body: VerifyOTPIn, response: Response):
    email = body.email.lower().strip()

    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        raise HTTPException(404, "User not found. Please request a new code.")

    ok, err = await verify_otp_via_external_service(email, body.otp.strip())
    if not ok:
        msg = (err or "").strip()
        if msg.lower() in ("invalid otp",):
            raise HTTPException(401, "Incorrect code. Please try again.")
        if msg.lower() == "expired":
            raise HTTPException(400, "Code expired. Please request a new one.")
        if msg.lower() == "no otp":
            raise HTTPException(400, "No active code. Please request a new one.")
        raise HTTPException(401, msg or "Verification failed.")

    await db.users.update_one({"email": email}, {"$set": {"email_verified": True}})
    user["email_verified"] = True

    access = create_access_token(user["id"], email)
    refresh = create_refresh_token(user["id"])
    set_auth_cookies(response, access, refresh)
    return {"user": public_user(user), "access_token": access, "refresh_token": refresh}


@api.post("/auth/dev-login")
async def dev_login(body: RequestOTPIn, response: Response):
    """Dev-only bypass for OTP. Issues a JWT without calling the external service.
    Enabled when env var DEV_LOGIN_ENABLED=true. Used by automated tests so the
    suite does not depend on real email delivery via the external OTP service.
    """
    if os.environ.get("DEV_LOGIN_ENABLED", "false").lower() not in ("true", "1", "yes"):
        raise HTTPException(404, "Not found")

    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        if not body.display_name or not body.display_name.strip():
            raise HTTPException(400, "display_name is required for new users")
        user = {
            "id": str(uuid.uuid4()),
            "email": email,
            "display_name": body.display_name.strip(),
            "avatar": None,
            "bio": "",
            "status": "Hey there! I'm using Vaanix.",
            "online": False,
            "last_seen": now_iso(),
            "email_verified": True,
            "blocked_users": [],
            "starred_messages": [],
            "muted_conversations": [],
            "role": "user",
            "created_at": now_iso(),
        }
        await db.users.insert_one(user.copy())
    else:
        await db.users.update_one({"email": email}, {"$set": {"email_verified": True}})
        user["email_verified"] = True

    access = create_access_token(user["id"], email)
    refresh = create_refresh_token(user["id"])
    set_auth_cookies(response, access, refresh)
    return {"user": public_user(user), "access_token": access, "refresh_token": refresh}


@api.post("/auth/logout")
async def logout(response: Response, current=Depends(get_current_user)):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    await db.users.update_one(
        {"id": current["id"]},
        {"$set": {"online": False, "last_seen": now_iso()}},
    )
    return {"ok": True}


@api.get("/auth/me")
async def me(current=Depends(get_current_user)):
    return public_user(current)


@api.post("/auth/refresh")
async def refresh_token(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(401, "No refresh token")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(401, "Invalid token type")
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
        if not user:
            raise HTTPException(401, "User not found")
        access = create_access_token(user["id"], user["email"])
        response.set_cookie("access_token", access, httponly=True, secure=False, samesite="lax",
                            max_age=ACCESS_TOKEN_MIN * 60, path="/")
        return {"access_token": access}
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid refresh token")


# --------------------------------------------------------------
# Users
# --------------------------------------------------------------
@api.get("/users")
async def list_users(q: Optional[str] = None, current=Depends(get_current_user)):
    query: Dict[str, Any] = {"id": {"$ne": current["id"]}}
    if q:
        query["$or"] = [
            {"display_name": {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}},
        ]
    users = await db.users.find(query, {"_id": 0, "password_hash": 0}).limit(200).to_list(200)
    blocked = set(current.get("blocked_users", []))
    return [public_user(u) for u in users if u["id"] not in blocked]


@api.put("/users/me")
async def update_me(body: ProfileIn, current=Depends(get_current_user)):
    update = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if update:
        await db.users.update_one({"id": current["id"]}, {"$set": update})
    user = await db.users.find_one({"id": current["id"]}, {"_id": 0, "password_hash": 0})
    return public_user(user)


@api.post("/users/{user_id}/block")
async def block_user(user_id: str, current=Depends(get_current_user)):
    await db.users.update_one({"id": current["id"]}, {"$addToSet": {"blocked_users": user_id}})
    return {"ok": True}


@api.post("/users/{user_id}/unblock")
async def unblock_user(user_id: str, current=Depends(get_current_user)):
    await db.users.update_one({"id": current["id"]}, {"$pull": {"blocked_users": user_id}})
    return {"ok": True}


@api.get("/users/blocked")
async def blocked_list(current=Depends(get_current_user)):
    ids = current.get("blocked_users", [])
    if not ids:
        return []
    users = await db.users.find({"id": {"$in": ids}}, {"_id": 0, "password_hash": 0}).to_list(200)
    return [public_user(u) for u in users]


# --------------------------------------------------------------
# Conversations & Messages
# --------------------------------------------------------------
async def _build_conversation(conv: Dict[str, Any], current_id: str) -> Dict[str, Any]:
    participants = await db.users.find(
        {"id": {"$in": conv["participants"]}}, {"_id": 0, "password_hash": 0}
    ).to_list(200)
    parts = [public_user(u) for u in participants]
    last = await db.messages.find_one(
        {"conversation_id": conv["id"], "deleted_for_all": {"$ne": True}},
        sort=[("created_at", -1)],
        projection={"_id": 0},
    )
    unread = await db.messages.count_documents({
        "conversation_id": conv["id"],
        "sender_id": {"$ne": current_id},
        "read_by": {"$ne": current_id},
    })
    return {
        "id": conv["id"],
        "type": conv["type"],
        "name": conv.get("name"),
        "avatar": conv.get("avatar"),
        "participants": parts,
        "admins": conv.get("admins", []),
        "created_by": conv.get("created_by"),
        "created_at": conv.get("created_at"),
        "muted": current_id in conv.get("muted_by", []),
        "last_message": last,
        "unread": unread,
    }


@api.get("/conversations")
async def list_conversations(current=Depends(get_current_user)):
    convs = await db.conversations.find(
        {"participants": current["id"]},
        {"_id": 0},
    ).sort("updated_at", -1).to_list(500)
    return [await _build_conversation(c, current["id"]) for c in convs]


@api.post("/conversations")
async def create_conversation(body: CreateConvIn, current=Depends(get_current_user)):
    parts = list({*body.participant_ids, current["id"]})
    if body.type == "direct":
        if len(parts) != 2:
            raise HTTPException(400, "Direct chat must have exactly 2 participants")
        existing = await db.conversations.find_one({
            "type": "direct",
            "participants": {"$all": parts, "$size": 2},
        }, {"_id": 0})
        if existing:
            return await _build_conversation(existing, current["id"])
    elif body.type == "group":
        if len(parts) < 2:
            raise HTTPException(400, "Group needs at least 2 participants")
        if not body.name:
            raise HTTPException(400, "Group name required")

    conv = {
        "id": str(uuid.uuid4()),
        "type": body.type,
        "participants": parts,
        "name": body.name,
        "avatar": body.avatar,
        "admins": [current["id"]] if body.type == "group" else [],
        "created_by": current["id"],
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "muted_by": [],
    }
    await db.conversations.insert_one(conv.copy())
    return await _build_conversation(conv, current["id"])


@api.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str, current=Depends(get_current_user)):
    conv = await db.conversations.find_one({"id": conv_id, "participants": current["id"]}, {"_id": 0})
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return await _build_conversation(conv, current["id"])


@api.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str, current=Depends(get_current_user)):
    conv = await db.conversations.find_one({"id": conv_id, "participants": current["id"]})
    if not conv:
        raise HTTPException(404, "Conversation not found")
    await db.conversations.delete_one({"id": conv_id})
    await db.messages.delete_many({"conversation_id": conv_id})
    return {"ok": True}


@api.post("/conversations/{conv_id}/mute")
async def mute_conv(conv_id: str, current=Depends(get_current_user)):
    await db.conversations.update_one(
        {"id": conv_id, "participants": current["id"]},
        {"$addToSet": {"muted_by": current["id"]}},
    )
    return {"ok": True}


@api.post("/conversations/{conv_id}/unmute")
async def unmute_conv(conv_id: str, current=Depends(get_current_user)):
    await db.conversations.update_one(
        {"id": conv_id, "participants": current["id"]},
        {"$pull": {"muted_by": current["id"]}},
    )
    return {"ok": True}


@api.post("/conversations/{conv_id}/participants/{user_id}")
async def add_participant(conv_id: str, user_id: str, current=Depends(get_current_user)):
    conv = await db.conversations.find_one({"id": conv_id})
    if not conv or conv["type"] != "group":
        raise HTTPException(404, "Group not found")
    if current["id"] not in conv.get("admins", []):
        raise HTTPException(403, "Only admins can add")
    await db.conversations.update_one({"id": conv_id}, {"$addToSet": {"participants": user_id}})
    new = await db.conversations.find_one({"id": conv_id}, {"_id": 0})
    return await _build_conversation(new, current["id"])


@api.delete("/conversations/{conv_id}/participants/{user_id}")
async def remove_participant(conv_id: str, user_id: str, current=Depends(get_current_user)):
    conv = await db.conversations.find_one({"id": conv_id})
    if not conv or conv["type"] != "group":
        raise HTTPException(404, "Group not found")
    if current["id"] not in conv.get("admins", []) and user_id != current["id"]:
        raise HTTPException(403, "Only admins can remove")
    await db.conversations.update_one({"id": conv_id}, {"$pull": {"participants": user_id, "admins": user_id}})
    new = await db.conversations.find_one({"id": conv_id}, {"_id": 0})
    if not new:
        return {"ok": True}
    return await _build_conversation(new, current["id"])


# Messages
@api.get("/conversations/{conv_id}/messages")
async def list_messages(
    conv_id: str,
    before: Optional[str] = None,
    limit: int = 50,
    current=Depends(get_current_user),
):
    conv = await db.conversations.find_one({"id": conv_id, "participants": current["id"]})
    if not conv:
        raise HTTPException(404, "Conversation not found")
    query: Dict[str, Any] = {"conversation_id": conv_id, "deleted_for": {"$ne": current["id"]}}
    if before:
        query["created_at"] = {"$lt": before}
    msgs = await db.messages.find(query, {"_id": 0}).sort("created_at", -1).limit(min(limit, 100)).to_list(100)
    msgs.reverse()
    # mark as read
    await db.messages.update_many(
        {"conversation_id": conv_id, "sender_id": {"$ne": current["id"]}, "read_by": {"$ne": current["id"]}},
        {"$addToSet": {"read_by": current["id"]}},
    )
    await broadcast_to_conv(conv_id, {"type": "read_receipt", "conversation_id": conv_id, "user_id": current["id"]})
    return msgs


@api.post("/conversations/{conv_id}/messages")
async def send_message(conv_id: str, body: SendMessageIn, current=Depends(get_current_user)):
    conv = await db.conversations.find_one({"id": conv_id, "participants": current["id"]})
    if not conv:
        raise HTTPException(404, "Conversation not found")
    msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conv_id,
        "sender_id": current["id"],
        "sender_name": current.get("display_name", ""),
        "type": body.type,
        "content": body.content,
        "file_name": body.file_name,
        "mime_type": body.mime_type,
        "duration": body.duration,
        "reply_to": body.reply_to,
        "reactions": [],   # list of {user_id, emoji}
        "read_by": [current["id"]],
        "delivered_to": [current["id"]],
        "starred_by": [],
        "deleted_for": [],
        "deleted_for_all": False,
        "created_at": now_iso(),
    }
    await db.messages.insert_one(msg.copy())
    await db.conversations.update_one({"id": conv_id}, {"$set": {"updated_at": now_iso()}})
    await broadcast_to_conv(conv_id, {"type": "new_message", "conversation_id": conv_id, "message": msg})
    return msg


@api.delete("/messages/{msg_id}")
async def delete_message(msg_id: str, for_all: bool = False, current=Depends(get_current_user)):
    msg = await db.messages.find_one({"id": msg_id})
    if not msg:
        raise HTTPException(404, "Message not found")
    if for_all:
        if msg["sender_id"] != current["id"]:
            raise HTTPException(403, "Only sender can delete for everyone")
        await db.messages.update_one({"id": msg_id}, {"$set": {"deleted_for_all": True, "content": ""}})
        await broadcast_to_conv(msg["conversation_id"], {"type": "message_deleted", "message_id": msg_id, "for_all": True})
    else:
        await db.messages.update_one({"id": msg_id}, {"$addToSet": {"deleted_for": current["id"]}})
    return {"ok": True}


@api.post("/messages/{msg_id}/react")
async def react(msg_id: str, body: ReactIn, current=Depends(get_current_user)):
    msg = await db.messages.find_one({"id": msg_id})
    if not msg:
        raise HTTPException(404, "Message not found")
    # Toggle: if same emoji from same user exists, remove. Else replace user's reaction.
    existing = next((r for r in msg.get("reactions", []) if r["user_id"] == current["id"]), None)
    if existing and existing["emoji"] == body.emoji:
        await db.messages.update_one({"id": msg_id}, {"$pull": {"reactions": {"user_id": current["id"]}}})
    else:
        await db.messages.update_one({"id": msg_id}, {"$pull": {"reactions": {"user_id": current["id"]}}})
        await db.messages.update_one({"id": msg_id}, {"$push": {"reactions": {"user_id": current["id"], "emoji": body.emoji, "name": current.get("display_name", "")}}})
    new = await db.messages.find_one({"id": msg_id}, {"_id": 0})
    await broadcast_to_conv(msg["conversation_id"], {"type": "message_updated", "message": new})
    return new


@api.post("/messages/{msg_id}/star")
async def star_message(msg_id: str, current=Depends(get_current_user)):
    msg = await db.messages.find_one({"id": msg_id})
    if not msg:
        raise HTTPException(404, "Message not found")
    is_starred = current["id"] in msg.get("starred_by", [])
    if is_starred:
        await db.messages.update_one({"id": msg_id}, {"$pull": {"starred_by": current["id"]}})
    else:
        await db.messages.update_one({"id": msg_id}, {"$addToSet": {"starred_by": current["id"]}})
    return {"ok": True, "starred": not is_starred}


@api.get("/messages/starred")
async def starred_messages(current=Depends(get_current_user)):
    msgs = await db.messages.find(
        {"starred_by": current["id"]}, {"_id": 0}
    ).sort("created_at", -1).limit(200).to_list(200)
    return msgs


@api.get("/messages/search")
async def search_messages(q: str, current=Depends(get_current_user)):
    if not q.strip():
        return []
    convs = await db.conversations.find({"participants": current["id"]}, {"_id": 0, "id": 1}).to_list(500)
    conv_ids = [c["id"] for c in convs]
    msgs = await db.messages.find({
        "conversation_id": {"$in": conv_ids},
        "type": "text",
        "content": {"$regex": q, "$options": "i"},
        "deleted_for_all": {"$ne": True},
        "deleted_for": {"$ne": current["id"]},
    }, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100)
    return msgs


# --------------------------------------------------------------
# WebSocket Manager
# --------------------------------------------------------------
class ConnectionManager:
    def __init__(self):
        self.active: Dict[str, Set[WebSocket]] = {}  # user_id -> sockets

    async def connect(self, user_id: str, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(user_id, set()).add(ws)
        await db.users.update_one({"id": user_id}, {"$set": {"online": True, "last_seen": now_iso()}})
        await self.broadcast_presence(user_id, True)

    async def disconnect(self, user_id: str, ws: WebSocket):
        if user_id in self.active:
            self.active[user_id].discard(ws)
            if not self.active[user_id]:
                self.active.pop(user_id, None)
                await db.users.update_one({"id": user_id}, {"$set": {"online": False, "last_seen": now_iso()}})
                await self.broadcast_presence(user_id, False)

    async def send_to_user(self, user_id: str, payload: dict):
        for ws in list(self.active.get(user_id, [])):
            try:
                await ws.send_text(json.dumps(payload, default=str))
            except Exception:
                pass

    async def broadcast_presence(self, user_id: str, online: bool):
        # tell all participants of any of this user's conversations
        convs = await db.conversations.find({"participants": user_id}, {"_id": 0, "participants": 1}).to_list(500)
        peers: Set[str] = set()
        for c in convs:
            for p in c.get("participants", []):
                if p != user_id:
                    peers.add(p)
        payload = {"type": "presence", "user_id": user_id, "online": online, "last_seen": now_iso()}
        for p in peers:
            await self.send_to_user(p, payload)


manager = ConnectionManager()


async def broadcast_to_conv(conv_id: str, payload: dict):
    conv = await db.conversations.find_one({"id": conv_id}, {"_id": 0, "participants": 1})
    if not conv:
        return
    for p in conv.get("participants", []):
        await manager.send_to_user(p, payload)


@app.websocket("/api/ws")
async def websocket_endpoint(ws: WebSocket, token: str = Query(...)):
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            await ws.close(code=4401)
            return
        user_id = payload["sub"]
    except jwt.PyJWTError:
        await ws.close(code=4401)
        return

    await manager.connect(user_id, ws)
    try:
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue
            mtype = msg.get("type")
            if mtype == "typing":
                conv_id = msg.get("conversation_id")
                if conv_id:
                    await broadcast_to_conv(conv_id, {
                        "type": "typing",
                        "conversation_id": conv_id,
                        "user_id": user_id,
                        "is_typing": bool(msg.get("is_typing")),
                    })
            elif mtype == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        await manager.disconnect(user_id, ws)
    except Exception as e:
        logger.exception(f"WS error: {e}")
        await manager.disconnect(user_id, ws)


# --------------------------------------------------------------
# App init
# --------------------------------------------------------------
@api.get("/")
async def root():
    return {"app": "Vaanix", "tagline": "Connect Beyond Words"}


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # mobile app uses Authorization Bearer; cookies still work locally
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    # indexes
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.conversations.create_index("id", unique=True)
    await db.conversations.create_index("participants")
    await db.messages.create_index("id", unique=True)
    await db.messages.create_index([("conversation_id", 1), ("created_at", -1)])
    # OTP TTL — auto-delete codes after expiry
    try:
        await db.otp_codes.create_index("expires_at", expireAfterSeconds=0)
    except Exception:
        pass
    await db.otp_codes.create_index("email")

    # One-time cleanup: remove the previously seeded users (now retired in OTP flow)
    await db.users.delete_many({
        "email": {"$in": ["admin@vaanix.app", "aarav@vaanix.app", "meera@vaanix.app"]}
    })

    logger.info("Vaanix API ready (OTP auth).")


@app.on_event("shutdown")
async def on_shutdown():
    client.close()
