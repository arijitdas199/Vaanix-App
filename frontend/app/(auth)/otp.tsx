import React, { useEffect, useRef, useState } from "react";
import {
  View, StyleSheet, TextInput, TouchableOpacity, KeyboardAvoidingView, Platform, ScrollView, ActivityIndicator,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { useRouter, useLocalSearchParams } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { Text } from "../../src/components/Text";
import { useTheme } from "../../src/lib/theme";
import { useAuth } from "../../src/lib/auth";
import { api } from "../../src/lib/api";

const LEN = 6;

export default function OtpScreen() {
  const { c } = useTheme();
  const router = useRouter();
  const params = useLocalSearchParams<{ email?: string; dev_otp?: string; email_sent?: string }>();
  const email = String(params.email || "");
  const devOtp = String(params.dev_otp || "");
  const emailSent = String(params.email_sent || "0") === "1";
  const { verifyOtp } = useAuth();

  const [digits, setDigits] = useState<string[]>(Array(LEN).fill(""));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [secondsLeft, setSecondsLeft] = useState(60);
  const [resending, setResending] = useState(false);
  const refs = useRef<Array<TextInput | null>>([]);

  useEffect(() => {
    refs.current[0]?.focus();
  }, []);

  useEffect(() => {
    const t = setInterval(() => setSecondsLeft((s) => (s > 0 ? s - 1 : 0)), 1000);
    return () => clearInterval(t);
  }, []);

  const setDigit = (idx: number, v: string) => {
    const cleaned = v.replace(/\D/g, "");
    if (cleaned.length > 1) {
      // pasted code
      const arr = cleaned.slice(0, LEN).split("");
      while (arr.length < LEN) arr.push("");
      setDigits(arr);
      const last = Math.min(cleaned.length, LEN) - 1;
      refs.current[Math.max(0, last)]?.focus();
      if (cleaned.length >= LEN) submit(arr.join(""));
      return;
    }
    const next = [...digits];
    next[idx] = cleaned;
    setDigits(next);
    if (cleaned && idx < LEN - 1) refs.current[idx + 1]?.focus();
    if (next.every((d) => d.length === 1)) submit(next.join(""));
  };

  const onKeyPress = (idx: number, key: string) => {
    if (key === "Backspace" && !digits[idx] && idx > 0) refs.current[idx - 1]?.focus();
  };

  const submit = async (code: string) => {
    setErr(null);
    setBusy(true);
    try {
      await verifyOtp(email, code);
      router.replace("/(tabs)/chats");
    } catch (e: any) {
      setErr(e?.message || "Invalid code");
      setDigits(Array(LEN).fill(""));
      refs.current[0]?.focus();
    } finally {
      setBusy(false);
    }
  };

  const resend = async () => {
    if (secondsLeft > 0 || resending) return;
    setResending(true);
    setErr(null);
    try {
      const res = await api.requestOtp(email);
      setSecondsLeft(60);
      if (res?.dev_otp) {
        // surface dev OTP for testing
        router.setParams({ dev_otp: res.dev_otp });
      }
    } catch (e: any) {
      setErr(e?.message || "Could not resend");
    } finally {
      setResending(false);
    }
  };

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: c.background }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <TouchableOpacity onPress={() => router.back()} style={styles.back}>
          <Ionicons name="chevron-back" size={26} color={c.textPrimary} />
        </TouchableOpacity>

        <Text variant="h1" style={{ marginTop: 12 }}>Check your inbox.</Text>
        <Text color={c.textSecondary} style={{ marginTop: 8, fontSize: 15, lineHeight: 22 }}>
          We sent a 6-digit code to{" "}
          <Text style={{ fontWeight: "700" }}>{email}</Text>. It expires in 5 minutes.
        </Text>

        {!emailSent && devOtp ? (
          <View style={[styles.devNote, { backgroundColor: c.surfaceVariant, borderColor: c.border }]}>
            <Ionicons name="construct" size={16} color={c.warning} />
            <View style={{ flex: 1 }}>
              <Text variant="caption" color={c.warning}>DEV MODE</Text>
              <Text variant="small" color={c.textSecondary} style={{ marginTop: 2 }}>
                Email could not be delivered (Resend test mode). Use this code:
              </Text>
              <Text testID="dev-otp" style={{ fontWeight: "800", fontSize: 22, letterSpacing: 6, marginTop: 6 }}>
                {devOtp}
              </Text>
            </View>
          </View>
        ) : null}

        <View style={styles.boxes}>
          {digits.map((d, i) => (
            <TextInput
              key={i}
              testID={`otp-${i}`}
              ref={(r) => { refs.current[i] = r; }}
              value={d}
              onChangeText={(v) => setDigit(i, v)}
              onKeyPress={(e) => onKeyPress(i, e.nativeEvent.key)}
              keyboardType="number-pad"
              maxLength={i === 0 ? LEN : 1}
              style={[styles.box, { backgroundColor: c.surfaceVariant, color: c.textPrimary, borderColor: d ? c.primary : c.border }]}
            />
          ))}
        </View>

        {err ? (
          <View style={[styles.err, { backgroundColor: c.error + "20" }]}>
            <Ionicons name="alert-circle" size={16} color={c.error} />
            <Text color={c.error} style={{ flex: 1 }} testID="otp-error">{err}</Text>
          </View>
        ) : null}

        <TouchableOpacity testID="otp-submit" disabled={busy || digits.some((d) => !d)} activeOpacity={0.9} onPress={() => submit(digits.join(""))} style={{ marginTop: 24 }}>
          <LinearGradient colors={c.gradient as any} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={[styles.primary, (busy || digits.some((d) => !d)) && { opacity: 0.6 }]}>
            {busy ? <ActivityIndicator color="#fff" /> : <Text color="#fff" style={{ fontWeight: "700", fontSize: 16 }}>Verify & continue</Text>}
          </LinearGradient>
        </TouchableOpacity>

        <View style={{ flexDirection: "row", justifyContent: "center", marginTop: 24, gap: 6 }}>
          <Text color={c.textSecondary}>Didn&apos;t get it?</Text>
          <TouchableOpacity testID="otp-resend" disabled={secondsLeft > 0 || resending} onPress={resend}>
            <Text color={secondsLeft > 0 ? c.textTertiary : c.primary} style={{ fontWeight: "700" }}>
              {resending ? "Sending…" : secondsLeft > 0 ? `Resend in ${secondsLeft}s` : "Resend code"}
            </Text>
          </TouchableOpacity>
        </View>

        <View style={{ flexDirection: "row", justifyContent: "center", marginTop: 16 }}>
          <TouchableOpacity onPress={() => router.replace("/(auth)/email")}>
            <Text color={c.textSecondary} variant="small">Change email</Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  scroll: { flexGrow: 1, padding: 24, paddingTop: 56 },
  back: { width: 36, height: 36, alignItems: "center", justifyContent: "center" },
  boxes: { flexDirection: "row", gap: 10, marginTop: 28, justifyContent: "center" },
  box: { width: 48, height: 56, borderRadius: 14, borderWidth: 1.5, textAlign: "center", fontSize: 22, fontWeight: "700" },
  devNote: { flexDirection: "row", gap: 12, padding: 14, borderRadius: 14, borderWidth: 1, marginTop: 24 },
  primary: { paddingVertical: 16, borderRadius: 16, alignItems: "center" },
  err: { flexDirection: "row", alignItems: "center", gap: 8, padding: 12, borderRadius: 12, marginTop: 16 },
});
