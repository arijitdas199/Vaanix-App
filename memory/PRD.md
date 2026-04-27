# Vaanix — Connect Beyond Words

## Overview
Vaanix is a real-time messaging mobile app built with Expo (React Native) + FastAPI + MongoDB + WebSockets. Premium indigo/violet Material 3 aesthetic with full Dark/Light theming.

## Tech Stack
- **Frontend:** Expo SDK 54, expo-router, react-native-reanimated, expo-linear-gradient, expo-image-picker, expo-document-picker, expo-av, expo-secure-store
- **Backend:** FastAPI, Motor (async MongoDB), PyJWT, native FastAPI WebSockets, **external OTP microservice** (Express + Resend) for email delivery and OTP verification
- **Storage:** MongoDB. Media stored as base64 data URLs.

## Implemented (MVP)
### Auth — Passwordless Email + OTP
- POST `/api/auth/request-otp` `{ email, display_name? }` — proxies to external OTP service which generates a 6-digit code, stores it in-memory (5-min TTL), and emails via Resend. Display name is required on first signup.
- POST `/api/auth/verify-otp` `{ email, otp }` — proxies to external OTP service for verification, then issues JWTs (access 7d, refresh 30d). Marks user `email_verified=true`.
- POST `/api/auth/dev-login` `{ email, display_name? }` — **dev-only bypass**, returns 404 unless `DEV_LOGIN_ENABLED=true`. Used by automated tests.
- JWT stored in `expo-secure-store` (mobile) / AsyncStorage (web)
- Legacy password endpoints removed

### External OTP Microservice
- URL configured via `OTP_BACKEND_URL` env (default: `https://otp-backend-lpv2.onrender.com`)
- Source: `https://github.com/arijitdas199/otp-backend.git`
- Exposes `POST /api/auth/request-otp` and `POST /api/auth/verify-otp`
- 5-minute OTP TTL maintained by the external service (in-memory Map)
- Emails delivered via Resend (`FROM_EMAIL` configured on the external service)

### Messaging (unchanged)
- 1-to-1 + group conversations (admin-controlled)
- Real-time delivery via WebSocket (`/api/ws?token=…`)
- Text, image, video, document, voice notes (base64)
- Reply, react (toggle), star, delete-for-me / delete-for-all, search
- Typing indicators, online presence + last seen, read receipts
- Mute/unmute conversations, block/unblock users

### UI
- Splash → Welcome → Email → OTP → Tabs (Chats / Calls / Settings)
- Floating action button for new chat / new group
- Rounded gradient bubbles with asymmetric radii
- Dark + Light + system theme
- Profile editor, Starred messages, Blocked contacts, Conversation info screens

## Architecture Notes
- All backend routes prefixed with `/api`. Auth via `Authorization: Bearer …` header or httpOnly cookies.
- WebSocket auth via `?token=…` query param. Server broadcasts: `new_message`, `message_updated`, `message_deleted`, `typing`, `presence`, `read_receipt`.
- IDs are UUID strings; all Mongo responses exclude `_id`.

## Environment Variables (backend/.env)
- `MONGO_URL`, `DB_NAME`
- `JWT_SECRET`
- `APP_NAME`
- `OTP_BACKEND_URL` — external OTP microservice base URL
- `DEV_LOGIN_ENABLED` — set to `true` to expose `/api/auth/dev-login` (off in production)

## Test Credentials
See `/app/memory/test_credentials.md`. Tests use the dev-login endpoint to bypass external OTP delivery.

## Smart Business Enhancement
A **shareable invite deep-link** for new groups (`vaanix://invite/{conv_id}`) — every group becomes a referral surface. Tiny add-on top of existing conversation IDs.
