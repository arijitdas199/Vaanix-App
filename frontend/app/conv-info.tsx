import React, { useEffect, useState } from "react";
import { View, StyleSheet, ScrollView, TouchableOpacity, Alert } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { Text } from "../src/components/Text";
import { Avatar } from "../src/components/Avatar";
import { useTheme } from "../src/lib/theme";
import { useAuth } from "../src/lib/auth";
import { api } from "../src/lib/api";

export default function ConvInfo() {
  const { c } = useTheme();
  const router = useRouter();
  const { user } = useAuth();
  const params = useLocalSearchParams<{ id: string }>();
  const id = String(params.id);
  const [conv, setConv] = useState<any>(null);

  const load = async () => { try { setConv(await api.getConv(id)); } catch {} };
  useEffect(() => { load(); }, [id]);

  if (!conv) return <SafeAreaView style={{ flex: 1, backgroundColor: c.background }} />;

  const peer = conv.type === "direct" ? conv.participants.find((p: any) => p.id !== user?.id) : null;
  const title = conv.type === "group" ? conv.name : peer?.display_name;
  const isAdmin = (conv.admins || []).includes(user?.id);

  const toggleMute = async () => {
    if (conv.muted) await api.unmuteConv(id); else await api.muteConv(id);
    load();
  };
  const block = async () => { if (peer) { await api.block(peer.id); router.replace("/(tabs)/chats"); } };
  const deleteChat = async () => { await api.deleteConv(id); router.replace("/(tabs)/chats"); };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.background }} edges={["top"]}>
      <View style={[styles.header, { borderBottomColor: c.border }]}>
        <TouchableOpacity onPress={() => router.back()}><Ionicons name="chevron-back" size={26} color={c.textPrimary} /></TouchableOpacity>
        <Text variant="h3" style={{ flex: 1, marginLeft: 8 }}>{conv.type === "group" ? "Group info" : "Contact info"}</Text>
      </View>
      <ScrollView contentContainerStyle={{ padding: 24 }}>
        <View style={{ alignItems: "center" }}>
          <Avatar name={title} uri={conv.type === "group" ? conv.avatar : peer?.avatar} size={120} online={!!peer?.online} />
          <Text variant="h2" style={{ marginTop: 16 }}>{title}</Text>
          {peer ? <Text color={c.textSecondary} style={{ marginTop: 4 }}>{peer.email}</Text> : null}
          {peer?.status ? <Text color={c.textSecondary} style={{ marginTop: 6, textAlign: "center" }}>{peer.status}</Text> : null}
        </View>

        <View style={{ marginTop: 28, backgroundColor: c.surface, borderRadius: 16, borderWidth: 1, borderColor: c.border, overflow: "hidden" }}>
          <Row icon={conv.muted ? "notifications" : "notifications-off-outline"} label={conv.muted ? "Unmute" : "Mute notifications"} onPress={toggleMute} />
          {conv.type === "group" ? (
            <View>
              <Row icon="people-outline" label={`${conv.participants.length} members`} />
              {conv.participants.map((p: any) => (
                <View key={p.id} style={[styles.row, { borderBottomColor: c.border }]}>
                  <Avatar name={p.display_name} uri={p.avatar} size={36} online={p.online} />
                  <Text style={{ flex: 1, marginLeft: 10 }}>{p.display_name}</Text>
                  {(conv.admins || []).includes(p.id) ? <Text variant="caption" color={c.primary}>Admin</Text> : null}
                </View>
              ))}
            </View>
          ) : null}
        </View>

        <View style={{ marginTop: 24, backgroundColor: c.surface, borderRadius: 16, borderWidth: 1, borderColor: c.border, overflow: "hidden" }}>
          {peer ? <Row icon="ban-outline" label="Block contact" danger onPress={block} testID="block-btn" /> : null}
          <Row icon="trash-outline" label={conv.type === "group" ? (isAdmin ? "Delete group" : "Leave group") : "Delete chat"} danger onPress={deleteChat} testID="delete-conv" />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function Row({ icon, label, onPress, danger, testID }: any) {
  const { c } = useTheme();
  return (
    <TouchableOpacity testID={testID} disabled={!onPress} onPress={onPress} style={[styles.row, { borderBottomColor: c.border }]}>
      <Ionicons name={icon} size={20} color={danger ? c.error : c.primary} />
      <Text style={{ flex: 1, marginLeft: 12, fontWeight: "600" }} color={danger ? c.error : undefined}>{label}</Text>
      {onPress ? <Ionicons name="chevron-forward" size={18} color={c.textTertiary} /> : null}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "center", padding: 14, gap: 8, borderBottomWidth: StyleSheet.hairlineWidth },
  row: { flexDirection: "row", alignItems: "center", padding: 14, borderBottomWidth: StyleSheet.hairlineWidth },
});
