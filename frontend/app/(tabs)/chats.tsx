import React, { useCallback, useEffect, useMemo, useState } from "react";
import { View, StyleSheet, FlatList, TouchableOpacity, RefreshControl, TextInput, Image } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { useRouter, useFocusEffect } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { SafeAreaView } from "react-native-safe-area-context";
import { Text } from "../../src/components/Text";
import { Avatar } from "../../src/components/Avatar";
import { useTheme } from "../../src/lib/theme";
import { useAuth } from "../../src/lib/auth";
import { api } from "../../src/lib/api";
import { useWS } from "../../src/lib/ws";

const EMPTY = "https://static.prod-images.emergentagent.com/jobs/e14f9429-60ef-4aba-b004-7f450f3decb4/images/5a3759bcd95956d9b315ef06d9482a3f4583bcecb6a05ddb121ea3d172e652e8.png";

function timeShort(iso?: string) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    const now = new Date();
    const sameDay = d.toDateString() === now.toDateString();
    if (sameDay) return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    const diff = (now.getTime() - d.getTime()) / 86400000;
    if (diff < 7) return d.toLocaleDateString([], { weekday: "short" });
    return d.toLocaleDateString([], { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}

export default function Chats() {
  const { c } = useTheme();
  const { user } = useAuth();
  const router = useRouter();
  const [convs, setConvs] = useState<any[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [q, setQ] = useState("");

  const load = useCallback(async () => {
    try {
      const data = await api.listConvs();
      setConvs(Array.isArray(data) ? data : []);
    } catch {}
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  useWS((msg) => {
    if (msg.type === "new_message" || msg.type === "presence" || msg.type === "message_updated") {
      load();
    }
  });

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return convs;
    return convs.filter((c2) => {
      const name = c2.type === "group" ? (c2.name || "").toLowerCase() : (c2.participants.find((p: any) => p.id !== user?.id)?.display_name || "").toLowerCase();
      return name.includes(s);
    });
  }, [convs, q, user?.id]);

  const renderItem = ({ item }: any) => {
    const peer = item.type === "direct" ? item.participants.find((p: any) => p.id !== user?.id) : null;
    const title = item.type === "group" ? item.name : peer?.display_name || "Chat";
    const last = item.last_message;
    const lastText =
      !last ? "Tap to start chatting"
      : last.deleted_for_all ? "🚫 Message deleted"
      : last.type === "text" ? last.content
      : last.type === "image" ? "📷 Photo"
      : last.type === "video" ? "🎬 Video"
      : last.type === "voice" ? "🎤 Voice note"
      : last.type === "document" ? `📎 ${last.file_name || "Document"}`
      : "Message";
    return (
      <TouchableOpacity
        testID={`chat-row-${item.id}`}
        activeOpacity={0.7}
        onPress={() => router.push({ pathname: "/chat/[id]", params: { id: item.id } })}
        style={[styles.row, { borderBottomColor: c.border }]}
      >
        <Avatar name={title} uri={item.type === "group" ? item.avatar : peer?.avatar} size={54} online={item.type === "direct" ? !!peer?.online : false} />
        <View style={{ flex: 1, marginLeft: 14 }}>
          <View style={{ flexDirection: "row", alignItems: "center" }}>
            <Text style={{ fontWeight: "700", flex: 1 }} numberOfLines={1}>{title}</Text>
            <Text variant="small" color={c.textTertiary}>{timeShort(last?.created_at || item.created_at)}</Text>
          </View>
          <View style={{ flexDirection: "row", alignItems: "center", marginTop: 4 }}>
            <Text color={c.textSecondary} numberOfLines={1} style={{ flex: 1, fontSize: 14 }}>{lastText}</Text>
            {item.unread > 0 ? (
              <View style={[styles.badge, { backgroundColor: c.secondary }]}>
                <Text color="#fff" style={{ fontSize: 11, fontWeight: "700" }}>{item.unread}</Text>
              </View>
            ) : null}
            {item.muted ? <Ionicons name="notifications-off" size={14} color={c.textTertiary} style={{ marginLeft: 6 }} /> : null}
          </View>
        </View>
      </TouchableOpacity>
    );
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.background }} edges={["top"]}>
      <View style={styles.header}>
        <View>
          <Text variant="h2" testID="chats-title">Vaanix</Text>
          <Text color={c.textTertiary} variant="small">Connect Beyond Words</Text>
        </View>
        <TouchableOpacity testID="open-starred" onPress={() => router.push("/starred")} style={[styles.iconBtn, { backgroundColor: c.surfaceVariant }]}>
          <Ionicons name="star" size={18} color={c.warning} />
        </TouchableOpacity>
      </View>

      <View style={[styles.search, { backgroundColor: c.surfaceVariant }]}>
        <Ionicons name="search" size={18} color={c.textTertiary} />
        <TextInput testID="chats-search" value={q} onChangeText={setQ} placeholder="Search chats" placeholderTextColor={c.textTertiary} style={[styles.searchInput, { color: c.textPrimary }]} />
      </View>

      <FlatList
        testID="chats-list"
        data={filtered}
        keyExtractor={(it) => it.id}
        renderItem={renderItem}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={c.primary} />}
        contentContainerStyle={filtered.length ? { paddingBottom: 120 } : { flexGrow: 1 }}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Image source={{ uri: EMPTY }} style={{ width: 220, height: 220 }} resizeMode="contain" />
            <Text variant="h3" style={{ marginTop: 16 }}>No conversations yet</Text>
            <Text color={c.textSecondary} style={{ textAlign: "center", marginTop: 8, paddingHorizontal: 32 }}>
              Tap the + button to start your first chat. Invite a friend by entering their email — they&apos;ll get a one-time code to join.
            </Text>
          </View>
        }
      />

      <TouchableOpacity testID="fab-new-chat" activeOpacity={0.85} onPress={() => router.push("/new-chat")} style={styles.fabWrap}>
        <LinearGradient colors={c.gradient as any} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.fab}>
          <Ionicons name="create" size={26} color="#fff" />
        </LinearGradient>
      </TouchableOpacity>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 20, paddingTop: 12, paddingBottom: 4 },
  iconBtn: { width: 40, height: 40, borderRadius: 20, alignItems: "center", justifyContent: "center" },
  search: { marginHorizontal: 20, marginVertical: 12, paddingHorizontal: 14, height: 44, borderRadius: 22, flexDirection: "row", alignItems: "center", gap: 10 },
  searchInput: { flex: 1, fontSize: 14 },
  row: { flexDirection: "row", alignItems: "center", paddingHorizontal: 20, paddingVertical: 14, borderBottomWidth: StyleSheet.hairlineWidth },
  badge: { minWidth: 22, height: 22, borderRadius: 11, alignItems: "center", justifyContent: "center", paddingHorizontal: 6, marginLeft: 8 },
  empty: { flex: 1, alignItems: "center", justifyContent: "center", paddingHorizontal: 24, paddingTop: 40 },
  fabWrap: { position: "absolute", right: 20, bottom: 24, shadowColor: "#6366F1", shadowOpacity: 0.5, shadowRadius: 16, shadowOffset: { width: 0, height: 8 }, elevation: 12 },
  fab: { width: 60, height: 60, borderRadius: 30, alignItems: "center", justifyContent: "center" },
});
