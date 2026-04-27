import React, { useState } from "react";
import {
  View, StyleSheet, TextInput, TouchableOpacity, KeyboardAvoidingView, Platform, ScrollView, ActivityIndicator,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { Text } from "../../src/components/Text";
import { useTheme } from "../../src/lib/theme";
import { api } from "../../src/lib/api";

export default function EmailEntry() {
  const { c } = useTheme();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [showName, setShowName] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const onContinue = async () => {
    setErr(null);
    const e = email.trim().toLowerCase();
    if (!e || !e.includes("@")) {
      setErr("Enter a valid email");
      return;
    }
    if (showName && !name.trim()) {
      setErr("Please tell us your name");
      return;
    }
    setBusy(true);
    try {
      const res = await api.requestOtp(e, showName ? name.trim() : undefined);
      router.push({
        pathname: "/(auth)/otp",
        params: { email: e, dev_otp: res?.dev_otp || "", email_sent: res?.email_sent ? "1" : "0" },
      });
    } catch (er: any) {
      const msg = er?.message || "Failed to send code";
      // Backend asks for display_name when user is new
      if (/display_name/i.test(msg)) {
        setShowName(true);
        setErr("Looks like you're new here — please enter your name to continue.");
      } else {
        setErr(msg);
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: c.background }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <TouchableOpacity onPress={() => router.back()} style={styles.back}>
          <Ionicons name="chevron-back" size={26} color={c.textPrimary} />
        </TouchableOpacity>

        <Text variant="h1" style={{ marginTop: 12 }}>What&apos;s your email?</Text>
        <Text color={c.textSecondary} style={{ marginTop: 8, fontSize: 15, lineHeight: 22 }}>
          We&apos;ll send a 6-digit code to verify it&apos;s you. No passwords. Ever.
        </Text>

        <View style={{ marginTop: 28 }}>
          <Text variant="caption" style={{ marginBottom: 8 }}>Email</Text>
          <View style={[styles.inputBox, { backgroundColor: c.surfaceVariant, borderColor: c.border }]}>
            <Ionicons name="mail-outline" size={18} color={c.textTertiary} />
            <TextInput
              testID="email-input"
              value={email}
              onChangeText={setEmail}
              placeholder="you@example.com"
              placeholderTextColor={c.textTertiary}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="email-address"
              style={[styles.input, { color: c.textPrimary }]}
            />
          </View>

          {showName ? (
            <View style={{ marginTop: 18 }}>
              <Text variant="caption" style={{ marginBottom: 8 }}>Display name</Text>
              <View style={[styles.inputBox, { backgroundColor: c.surfaceVariant, borderColor: c.border }]}>
                <Ionicons name="person-outline" size={18} color={c.textTertiary} />
                <TextInput
                  testID="name-input"
                  value={name}
                  onChangeText={setName}
                  placeholder="Your name"
                  placeholderTextColor={c.textTertiary}
                  style={[styles.input, { color: c.textPrimary }]}
                />
              </View>
            </View>
          ) : null}
        </View>

        {err ? (
          <View style={[styles.err, { backgroundColor: c.error + "20" }]}>
            <Ionicons name="information-circle" size={16} color={c.error} />
            <Text color={c.error} style={{ flex: 1 }} testID="email-error">{err}</Text>
          </View>
        ) : null}

        <TouchableOpacity testID="email-continue" disabled={busy} activeOpacity={0.9} onPress={onContinue} style={{ marginTop: 24 }}>
          <LinearGradient colors={c.gradient as any} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.primary}>
            {busy ? <ActivityIndicator color="#fff" /> : <Text color="#fff" style={{ fontWeight: "700", fontSize: 16 }}>Send code</Text>}
          </LinearGradient>
        </TouchableOpacity>

        <Text color={c.textTertiary} variant="small" style={{ textAlign: "center", marginTop: 24, lineHeight: 18 }}>
          By continuing, you agree to Vaanix&apos;s Terms of Service and Privacy Policy.
        </Text>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  scroll: { flexGrow: 1, padding: 24, paddingTop: 56 },
  back: { width: 36, height: 36, alignItems: "center", justifyContent: "center" },
  inputBox: { flexDirection: "row", alignItems: "center", gap: 10, height: 52, paddingHorizontal: 16, borderRadius: 14, borderWidth: 1 },
  input: { flex: 1, fontSize: 15 },
  primary: { paddingVertical: 16, borderRadius: 16, alignItems: "center" },
  err: { flexDirection: "row", alignItems: "center", gap: 8, padding: 12, borderRadius: 12, marginTop: 16 },
});
