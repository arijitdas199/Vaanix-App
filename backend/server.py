from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import uuid
import json
import random
import asyncio
import logging
import secrets
import jwt
import resend
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
OTP_TTL_MIN = 5
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN_SEC = 60

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

# Resend
resend.api_key = os.environ.get("RESEND_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
APP_NAME = os.environ.get("APP_NAME", "Vaanix")
DEV_RETURN_OTP = os.environ.get("DEV_RETURN_OTP", "false").lower() in ("true", "1", "yes")

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
    return f"{random.randint(0, 999999):06d}"


def _otp_email_html(otp: str) -> str:
    return f"""
    <html><body style="margin:0;padding:0;background:#0A0B10;font-family:Arial,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#0A0B10;padding:40px 20px;">
        <tr><td align="center">
          <table width="480" cellpadding="0" cellspacing="0" style="background:#12141D;border-radius:18px;padding:36px;border:1px solid #272A37;">
            <tr><td align="center" style="padding-bottom:24px;">
              <table cellpadding="0" cellspacing="0"><tr>
                <td style="background:linear-gradient(135deg,#6366F1,#A78BFA);width:48px;height:48px;border-radius:14px;text-align:center;color:#fff;font-size:22px;font-weight:bold;line-height:48px;">V</td>
                <td style="padding-left:12px;color:#F8FAFC;font-size:24px;font-weight:bold;">{APP_NAME}</td>
              </tr></table>
            </td></tr>
            <tr><td align="center" style="color:#F8FAFC;font-size:22px;font-weight:600;padding-bottom:12px;">Your sign-in code</td></tr>
            <tr><td align="center" style="color:#94A3B8;font-size:14px;line-height:22px;padding-bottom:24px;">Use the code below to continue. It expires in {OTP_TTL_MIN} minutes.</td></tr>
            <tr><td align="center" style="padding-bottom:28px;">
              <div style="display:inline-block;background:#1E202B;border:1px solid #272A37;border-radius:14px;padding:18px 28px;color:#F8FAFC;font-size:34px;letter-spacing:10px;font-weight:700;">{otp}</div>
            </td></tr>
            <tr><td align="center" style="color:#64748B;font-size:12px;line-height:18px;">If you didn't request this code, just ignore this email. Someone may have entered your email by mistake.</td></tr>
            <tr><td align="center" style="padding-top:28px;color:#475569;font-size:11px;">Connect Beyond Words — {APP_NAME}</td></tr>
          </table>
        </td></tr>
      </table>
    </body></html>
    """


async def send_otp_email(to_email: str, otp: str) -> Optional[str]:
    if not resend.api_key:
        logger.warning("RESEND_API_KEY not set — skipping email send.")
        return None
    params = {
        "from": SENDER_EMAIL,
        "to": [to_email],
        "subject": f"{APP_NAME} sign-in code: {otp}",
        "html": _otp_email_html(otp),
    }
    try:
        result = await asyncio.to_thread(resend.Emails.send, params)
        return result.get("id") if isinstance(result, dict) else None
    except Exception as e:
        logger.error(f"Resend send failed for {to_email}: {e}")
        return None


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

    # Cooldown: only one OTP per minute per email
    last = await db.otp_codes.find_one({"email": email}, sort=[("created_at", -1)])
    if last:
        last_at = datetime.fromisoformat(last["created_at"])
        if (now_utc() - last_at).total_seconds() < OTP_RESEND_COOLDOWN_SEC:
            wait = OTP_RESEND_COOLDOWN_SEC - int((now_utc() - last_at).total_seconds())
            raise HTTPException(429, f"Please wait {wait}s before requesting a new code")

    # Invalidate any prior unused codes
    await db.otp_codes.delete_many({"email": email})

    otp = gen_otp()
    expires_at = now_utc() + timedelta(minutes=OTP_TTL_MIN)
    await db.otp_codes.insert_one({
        "email": email,
        "otp": otp,
        "attempts": 0,
        "used": False,
        "expires_at": expires_at,
        "created_at": now_iso(),
    })

    email_id = await send_otp_email(email, otp)
    logger.info(f"[OTP] {email} -> {otp} (resend_id={email_id})")

    payload: Dict[str, Any] = {
        "ok": True,
        "message": "Verification code sent to your email.",
        "expires_in": OTP_TTL_MIN * 60,
        "is_new_user": user.get("email_verified") is False,
        "email_sent": bool(email_id),
    }
    if DEV_RETURN_OTP:
        payload["dev_otp"] = otp
    return payload


@api.post("/auth/verify-otp")
async def verify_otp(body: VerifyOTPIn, response: Response):
    email = body.email.lower().strip()
    rec = await db.otp_codes.find_one({"email": email, "used": False}, sort=[("created_at", -1)])
    if not rec:
        raise HTTPException(400, "No active code. Please request a new one.")

    expires_at = rec["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now_utc():
        await db.otp_codes.delete_one({"_id": rec["_id"]})
        raise HTTPException(400, "Code expired. Please request a new one.")

    if rec.get("attempts", 0) >= OTP_MAX_ATTEMPTS:
        await db.otp_codes.delete_one({"_id": rec["_id"]})
        raise HTTPException(429, "Too many incorrect attempts. Please request a new code.")

    if rec["otp"] != body.otp.strip():
        await db.otp_codes.update_one({"_id": rec["_id"]}, {"$inc": {"attempts": 1}})
        remaining = OTP_MAX_ATTEMPTS - (rec.get("attempts", 0) + 1)
        raise HTTPException(401, f"Incorrect code. {max(remaining, 0)} attempts left.")

    await db.otp_codes.update_one({"_id": rec["_id"]}, {"$set": {"used": True}})
    await db.users.update_one({"email": email}, {"$set": {"email_verified": True}})

    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        raise HTTPException(404, "User not found")

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
