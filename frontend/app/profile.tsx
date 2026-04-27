import React, { useState } from "react";
import { View, StyleSheet, TouchableOpacity, ScrollView, TextInput, ActivityIndicator } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import * as ImagePicker from "expo-image-picker";
import { LinearGradient } from "expo-linear-gradient";
import { Text } from "../src/components/Text";
import { Avatar } from "../src/components/Avatar";
import { useTheme } from "../src/lib/theme";
import { useAuth } from "../src/lib/auth";
import { api } from "../src/lib/api";

export default function Profile() {
  const { c } = useTheme();
  const router = useRouter();
  const { user, refreshMe } = useAuth();
  const [name, setName] = useState(user?.display_name || "");
  const [bio, setBio] = useState(user?.bio || "");
  const [status, setStatus] = useState(user?.status || "");
  const [avatar, setAvatar] = useState<string | null | undefined>(user?.avatar);
  const [busy, setBusy] = useState(false);

  const pick = async () => {
    const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ImagePicker.MediaTypeOptions.Images, base64: true, allowsEditing: true, aspect: [1, 1], quality: 0.5 });
    if (r.canceled || !r.assets?.[0]) return;
    setAvatar(`data:${r.assets[0].mimeType || "image/jpeg"};base64,${r.assets[0].base64}`);
  };

  const save = async () => {
    setBusy(true);
    try { await api.updateMe({ display_name: name, bio, status, avatar }); await refreshMe(); router.back(); } catch {} finally { setBusy(false); }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.background }} edges={["top"]}>
      <View style={[styles.header, { borderBottomColor: c.border }]}>
        <TouchableOpacity onPress={() => router.back()}><Ionicons name="chevron-back" size={26} color={c.textPrimary} /></TouchableOpacity>
        <Text variant="h3" style={{ flex: 1, marginLeft: 8 }}>Edit profile</Text>
      </View>

      <ScrollView contentContainerStyle={{ padding: 24 }}>
        <View style={{ alignItems: "center", marginBottom: 24 }}>
          <TouchableOpacity testID="profile-avatar-btn" onPress={pick} activeOpacity={0.85}>
            <Avatar name={name} uri={avatar} size={120} />
            <View style={[styles.editBadge, { backgroundColor: c.primary }]}><Ionicons name="camera" size={16} color="#fff" /></View>
          </TouchableOpacity>
        </View>

        <Text variant="caption" style={{ marginBottom: 6 }}>Display name</Text>
        <TextInput testID="profile-name" value={name} onChangeText={setName} style={[styles.input, { backgroundColor: c.surfaceVariant, color: c.textPrimary, borderColor: c.border }]} placeholderTextColor={c.textTertiary} />

        <Text variant="caption" style={{ marginBottom: 6, marginTop: 14 }}>Status</Text>
        <TextInput testID="profile-status" value={status} onChangeText={setStatus} placeholder="Hey there! I'm using Vaanix." placeholderTextColor={c.textTertiary} style={[styles.input, { backgroundColor: c.surfaceVariant, color: c.textPrimary, borderColor: c.border }]} />

        <Text variant="caption" style={{ marginBottom: 6, marginTop: 14 }}>Bio</Text>
        <TextInput testID="profile-bio" value={bio} onChangeText={setBio} placeholder="A few words about you" placeholderTextColor={c.textTertiary} multiline style={[styles.input, { backgroundColor: c.surfaceVariant, color: c.textPrimary, borderColor: c.border, height: 100, paddingTop: 12, textAlignVertical: "top" }]} />

        <TouchableOpacity testID="profile-save" onPress={save} disabled={busy} activeOpacity={0.9} style={{ marginTop: 28 }}>
          <LinearGradient colors={c.gradient as any} style={styles.cta}>
            {busy ? <ActivityIndicator color="#fff" /> : <Text color="#fff" style={{ fontWeight: "700" }}>Save</Text>}
          </LinearGradient>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "center", padding: 14, gap: 8, borderBottomWidth: StyleSheet.hairlineWidth },
  input: { padding: 14, borderRadius: 14, borderWidth: 1, fontSize: 15 },
  cta: { paddingVertical: 16, borderRadius: 14, alignItems: "center" },
  editBadge: { position: "absolute", right: 0, bottom: 0, width: 36, height: 36, borderRadius: 18, alignItems: "center", justifyContent: "center", borderWidth: 3, borderColor: "#fff" },
});
