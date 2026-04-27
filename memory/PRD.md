# Vaanix — Connect Beyond Words

## Overview
Vaanix is a real-time messaging mobile app built with Expo (React Native) + FastAPI + MongoDB + WebSockets. Premium indigo/violet Material 3 aesthetic with full Dark/Light theming.

## Tech Stack
- **Frontend:** Expo SDK 54, expo-router, react-native-reanimated, expo-linear-gradient, expo-image-picker, expo-document-picker, expo-av, expo-secure-store
- **Backend:** FastAPI, Motor (async MongoDB), PyJWT, native FastAPI WebSockets, Resend (transactional email)
- **Storage:** MongoDB. Media stored as base64 data URLs.

## Implemented (MVP)
### Auth — Passwordless Email + OTP
- POST `/api/auth/request-otp` `{ email, display_name? }` — generates 6-digit code, sends via Resend, returns `dev_otp` in dev mode for fallback testing
- POST `/api/auth/verify-otp` `{ email, otp }` — exchanges valid OTP for JWT (access 7d, refresh 30d). Marks user `email_verified=true`.
- 5-minute OTP TTL, max 5 verify attempts, 60-second resend cooldown
- JWT stored in `expo-secure-store` (mobile) / AsyncStorage (web)
- Legacy password endpoints removed

### Email Delivery
- Provider: **Resend** (`onboarding@resend.dev` — test mode delivers only to the Resend account-verified email)
- For all other emails, the OTP is returned in the API response and surfaced via a "DEV MODE" banner in the app
- To enable production-grade delivery to any email: verify a domain at https://resend.com/domains and update `SENDER_EMAIL` in `/app/backend/.env`

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

## Mocked / Deferred
- **Resend**: real email integration is in place. In Resend test mode, delivery to non-verified recipients fails by design; the OTP is returned in the API response so the app remains testable. Verify a domain in Resend to enable production delivery to any address.
- **Deferred:** voice/video calls, multi-device sync, message forwarding, end-to-end encryption, native FCM (requires EAS dev build).

## Test Credentials
See `/app/memory/test_credentials.md`. There are no static accounts — sign up with any email; OTP is delivered to your Resend-verified inbox or surfaced in the API/UI in dev mode.

## Smart Business Enhancement
A **shareable invite deep-link** for new groups (`vaanix://invite/{conv_id}`) — every group becomes a referral surface. Tiny add-on top of existing conversation IDs.
