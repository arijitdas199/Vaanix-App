import React, { useCallback, useEffect, useState } from "react";
import { View, StyleSheet, FlatList, TouchableOpacity, TextInput, ActivityIndicator } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import { Text } from "../src/components/Text";
import { Avatar } from "../src/components/Avatar";
import { useTheme } from "../src/lib/theme";
import { api } from "../src/lib/api";

export default function NewChat() {
  const { c } = useTheme();
  const router = useRouter();
  const [users, setUsers] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [groupMode, setGroupMode] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [groupName, setGroupName] = useState("");

  const load = useCallback(async () => {
    setBusy(true);
    try { setUsers(await api.listUsers(q)); } catch {} finally { setBusy(false); }
  }, [q]);

  useEffect(() => { const t = setTimeout(load, 200); return () => clearTimeout(t); }, [load]);

  const startDirect = async (uid: string) => {
    try {
      const conv = await api.createConv({ type: "direct", participant_ids: [uid] });
      router.replace({ pathname: "/chat/[id]", params: { id: conv.id } });
    } catch {}
  };

  const createGroup = async () => {
    if (!groupName.trim() || selected.length < 1) return;
    try {
      const conv = await api.createConv({ type: "group", participant_ids: selected, name: groupName.trim() });
      router.replace({ pathname: "/chat/[id]", params: { id: conv.id } });
    } catch {}
  };

  const toggle = (id: string) => setSelected((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id]);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.background }} edges={["top"]}>
      <View style={[styles.header, { borderBottomColor: c.border }]}>
        <TouchableOpacity onPress={() => router.back()}><Ionicons name="chevron-back" size={26} color={c.textPrimary} /></TouchableOpacity>
        <Text variant="h3" style={{ flex: 1, marginLeft: 8 }}>{groupMode ? "New group" : "New chat"}</Text>
        <TouchableOpacity testID="toggle-group" onPress={() => { setGroupMode(!groupMode); setSelected([]); }}>
          <Ionicons name={groupMode ? "person-outline" : "people-outline"} size={22} color={c.primary} />
        </TouchableOpacity>
      </View>

      <View style={{ padding: 16, gap: 10 }}>
        {groupMode ? (
          <TextInput testID="group-name-input" value={groupName} onChangeText={setGroupName} placeholder="Group name" placeholderTextColor={c.textTertiary} style={[styles.input, { backgroundColor: c.surfaceVariant, color: c.textPrimary }]} />
        ) : null}
        <View style={[styles.input, { backgroundColor: c.surfaceVariant, flexDirection: "row", alignItems: "center", gap: 10 }]}>
          <Ionicons name="search" size={18} color={c.textTertiary} />
          <TextInput testID="search-users" value={q} onChangeText={setQ} placeholder="Search users" placeholderTextColor={c.textTertiary} style={{ flex: 1, color: c.textPrimary }} />
        </View>
      </View>

      {busy ? <ActivityIndicator color={c.primary} /> : null}
      <FlatList
        data={users}
        keyExtractor={(it) => it.id}
        renderItem={({ item }) => {
          const sel = selected.includes(item.id);
          return (
            <TouchableOpacity testID={`user-row-${item.id}`} onPress={() => groupMode ? toggle(item.id) : startDirect(item.id)} activeOpacity={0.7} style={[styles.row, { borderBottomColor: c.border }]}>
              <Avatar name={item.display_name} uri={item.avatar} size={48} online={item.online} />
              <View style={{ flex: 1, marginLeft: 12 }}>
                <Text style={{ fontWeight: "700" }}>{item.display_name}</Text>
                <Text variant="small" color={c.textSecondary} numberOfLines={1}>{item.status || item.email}</Text>
              </View>
              {groupMode ? (
                <View style={[styles.check, { borderColor: sel ? c.primary : c.border, backgroundColor: sel ? c.primary : "transparent" }]}>
                  {sel ? <Ionicons name="checkmark" size={16} color="#fff" /> : null}
                </View>
              ) : null}
            </TouchableOpacity>
          );
        }}
        ListEmptyComponent={!busy ? <Text color={c.textTertiary} style={{ textAlign: "center", marginTop: 32 }}>No users found</Text> : null}
      />

      {groupMode && selected.length > 0 ? (
        <TouchableOpacity testID="create-group-btn" onPress={createGroup} activeOpacity={0.9} style={{ margin: 16 }}>
          <LinearGradient colors={c.gradient as any} style={styles.cta}>
            <Text color="#fff" style={{ fontWeight: "700" }}>Create group ({selected.length})</Text>
          </LinearGradient>
        </TouchableOpacity>
      ) : null}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "center", padding: 14, gap: 8, borderBottomWidth: StyleSheet.hairlineWidth },
  input: { paddingHorizontal: 14, height: 46, borderRadius: 14, fontSize: 15 },
  row: { flexDirection: "row", alignItems: "center", padding: 14, borderBottomWidth: StyleSheet.hairlineWidth },
  check: { width: 24, height: 24, borderRadius: 12, borderWidth: 2, alignItems: "center", justifyContent: "center" },
  cta: { paddingVertical: 14, borderRadius: 14, alignItems: "center" },
});
