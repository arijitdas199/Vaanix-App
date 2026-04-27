import * as SecureStore from "expo-secure-store";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { Platform } from "react-native";

const KEY = "vaanix_token";

const isWeb = Platform.OS === "web";

export async function saveToken(token: string) {
  if (isWeb) await AsyncStorage.setItem(KEY, token);
  else await SecureStore.setItemAsync(KEY, token);
}

export async function getToken(): Promise<string | null> {
  if (isWeb) return AsyncStorage.getItem(KEY);
  return SecureStore.getItemAsync(KEY);
}

export async function clearToken() {
  if (isWeb) await AsyncStorage.removeItem(KEY);
  else await SecureStore.deleteItemAsync(KEY);
}

export const BASE_URL = process.env.EXPO_PUBLIC_BACKEND_URL || "";

async function authedFetch(path: string, options: RequestInit = {}) {
  const token = await getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as any),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers, credentials: "include" });
  let data: any = null;
  const text = await res.text();
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    const detail = data?.detail;
    const msg =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
        ? detail.map((e: any) => e?.msg ?? JSON.stringify(e)).join(", ")
        : data?.message || `Request failed (${res.status})`;
    throw new Error(msg);
  }
  return data;
}

export const api = {
  // auth (OTP-based)
  requestOtp: (email: string, display_name?: string) =>
    authedFetch("/api/auth/request-otp", { method: "POST", body: JSON.stringify({ email, display_name }) }),
  verifyOtp: (email: string, otp: string) =>
    authedFetch("/api/auth/verify-otp", { method: "POST", body: JSON.stringify({ email, otp }) }),
  logout: () => authedFetch("/api/auth/logout", { method: "POST" }),
  me: () => authedFetch("/api/auth/me"),

  // users
  listUsers: (q?: string) => authedFetch(`/api/users${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  updateMe: (body: any) => authedFetch("/api/users/me", { method: "PUT", body: JSON.stringify(body) }),
  block: (uid: string) => authedFetch(`/api/users/${uid}/block`, { method: "POST" }),
  unblock: (uid: string) => authedFetch(`/api/users/${uid}/unblock`, { method: "POST" }),
  blockedList: () => authedFetch("/api/users/blocked"),

  // conversations
  listConvs: () => authedFetch("/api/conversations"),
  createConv: (body: any) => authedFetch("/api/conversations", { method: "POST", body: JSON.stringify(body) }),
  getConv: (id: string) => authedFetch(`/api/conversations/${id}`),
  deleteConv: (id: string) => authedFetch(`/api/conversations/${id}`, { method: "DELETE" }),
  muteConv: (id: string) => authedFetch(`/api/conversations/${id}/mute`, { method: "POST" }),
  unmuteConv: (id: string) => authedFetch(`/api/conversations/${id}/unmute`, { method: "POST" }),
  addParticipant: (id: string, uid: string) => authedFetch(`/api/conversations/${id}/participants/${uid}`, { method: "POST" }),
  removeParticipant: (id: string, uid: string) => authedFetch(`/api/conversations/${id}/participants/${uid}`, { method: "DELETE" }),

  // messages
  listMessages: (convId: string, before?: string) =>
    authedFetch(`/api/conversations/${convId}/messages${before ? `?before=${encodeURIComponent(before)}` : ""}`),
  sendMessage: (convId: string, body: any) =>
    authedFetch(`/api/conversations/${convId}/messages`, { method: "POST", body: JSON.stringify(body) }),
  deleteMessage: (id: string, forAll = false) =>
    authedFetch(`/api/messages/${id}?for_all=${forAll}`, { method: "DELETE" }),
  react: (id: string, emoji: string) =>
    authedFetch(`/api/messages/${id}/react`, { method: "POST", body: JSON.stringify({ emoji }) }),
  star: (id: string) => authedFetch(`/api/messages/${id}/star`, { method: "POST" }),
  starred: () => authedFetch("/api/messages/starred"),
  search: (q: string) => authedFetch(`/api/messages/search?q=${encodeURIComponent(q)}`),
};
