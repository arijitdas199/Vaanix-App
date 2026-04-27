import React, { useState } from "react";
import { View, StyleSheet, TouchableOpacity, ScrollView, Switch, Alert } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { Text } from "../../src/components/Text";
import { Avatar } from "../../src/components/Avatar";
import { useTheme } from "../../src/lib/theme";
import { useAuth } from "../../src/lib/auth";

export default function Settings() {
  const { c, mode, setMode, isDark } = useTheme();
  const { user, logout } = useAuth();
  const router = useRouter();
  const [confirmLogout, setConfirmLogout] = useState(false);

  const Section: React.FC<{ children: React.ReactNode; title?: string }> = ({ children, title }) => (
    <View style={{ marginTop: 22 }}>
      {title ? <Text variant="caption" style={{ marginHorizontal: 20, marginBottom: 8 }}>{title}</Text> : null}
      <View style={{ marginHorizontal: 16, backgroundColor: c.surface, borderRadius: 18, overflow: "hidden", borderWidth: 1, borderColor: c.border }}>{children}</View>
    </View>
  );

  const Item: React.FC<{ icon: any; label: string; onPress?: () => void; right?: React.ReactNode; danger?: boolean; testID?: string }> = ({ icon, label, onPress, right, danger, testID }) => (
    <TouchableOpacity testID={testID} disabled={!onPress} activeOpacity={0.7} onPress={onPress} style={[styles.row, { borderBottomColor: c.border }]}>
      <View style={[styles.iconBox, { backgroundColor: (danger ? c.error : c.primary) + "20" }]}>
        <Ionicons name={icon} size={18} color={danger ? c.error : c.primary} />
      </View>
      <Text style={{ flex: 1, fontWeight: "600" }} color={danger ? c.error : undefined}>{label}</Text>
      {right || (onPress ? <Ionicons name="chevron-forward" size={18} color={c.textTertiary} /> : null)}
    </TouchableOpacity>
  );

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.background }} edges={["top"]}>
      <ScrollView contentContainerStyle={{ paddingBottom: 120 }}>
        <View style={{ paddingHorizontal: 20, paddingTop: 12 }}>
          <Text variant="h2">Settings</Text>
        </View>

        <TouchableOpacity testID="open-profile" onPress={() => router.push("/profile")} activeOpacity={0.7} style={[styles.profileCard, { backgroundColor: c.surface, borderColor: c.border }]}>
          <Avatar name={user?.display_name} uri={user?.avatar} size={64} online />
          <View style={{ flex: 1, marginLeft: 14 }}>
            <Text style={{ fontWeight: "700", fontSize: 18 }}>{user?.display_name || "—"}</Text>
            <Text color={c.textSecondary} numberOfLines={1} style={{ marginTop: 2 }}>{user?.status || ""}</Text>
            <Text color={c.textTertiary} variant="small" style={{ marginTop: 2 }}>{user?.email}</Text>
          </View>
          <Ionicons name="chevron-forward" size={20} color={c.textTertiary} />
        </TouchableOpacity>

        <Section title="Appearance">
          <Item icon="moon-outline" label="Dark mode" right={<Switch testID="toggle-dark" value={isDark} onValueChange={(v) => setMode(v ? "dark" : "light")} trackColor={{ true: c.primary }} />} />
          <Item icon="phone-portrait-outline" label="Use system theme" right={<Switch value={mode === "system"} onValueChange={(v) => setMode(v ? "system" : isDark ? "dark" : "light")} trackColor={{ true: c.primary }} />} />
        </Section>

        <Section title="Privacy">
          <Item testID="settings-blocked" icon="ban-outline" label="Blocked contacts" onPress={() => router.push("/blocked")} />
          <Item testID="settings-starred" icon="star-outline" label="Starred messages" onPress={() => router.push("/starred")} />
        </Section>

        <Section title="About">
          <Item icon="information-circle-outline" label="Vaanix v1.0" />
          <Item icon="shield-checkmark-outline" label="Privacy & security" />
        </Section>

        <Section>
          {!confirmLogout ? (
            <Item testID="settings-logout" icon="log-out-outline" label="Log out" danger onPress={() => setConfirmLogout(true)} />
          ) : (
            <View style={{ padding: 16 }}>
              <Text>Are you sure you want to log out?</Text>
              <View style={{ flexDirection: "row", gap: 10, marginTop: 12 }}>
                <TouchableOpacity onPress={() => setConfirmLogout(false)} style={[styles.btn, { backgroundColor: c.surfaceVariant }]}>
                  <Text style={{ fontWeight: "600" }}>Cancel</Text>
                </TouchableOpacity>
                <TouchableOpacity testID="confirm-logout" onPress={async () => { await logout(); router.replace("/(auth)/welcome"); }} style={[styles.btn, { backgroundColor: c.error }]}>
                  <Text color="#fff" style={{ fontWeight: "700" }}>Log out</Text>
                </TouchableOpacity>
              </View>
            </View>
          )}
        </Section>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  profileCard: { flexDirection: "row", alignItems: "center", marginHorizontal: 16, marginTop: 18, padding: 16, borderRadius: 18, borderWidth: 1 },
  row: { flexDirection: "row", alignItems: "center", padding: 14, gap: 12, borderBottomWidth: StyleSheet.hairlineWidth },
  iconBox: { width: 36, height: 36, borderRadius: 10, alignItems: "center", justifyContent: "center" },
  btn: { flex: 1, padding: 12, borderRadius: 12, alignItems: "center" },
});
