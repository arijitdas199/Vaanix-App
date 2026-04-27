import React, { useCallback, useEffect, useState } from "react";
import { View, StyleSheet, FlatList, TouchableOpacity } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { Text } from "../src/components/Text";
import { Avatar } from "../src/components/Avatar";
import { useTheme } from "../src/lib/theme";
import { api } from "../src/lib/api";

export default function Blocked() {
  const { c } = useTheme();
  const router = useRouter();
  const [items, setItems] = useState<any[]>([]);
  const load = useCallback(async () => { try { setItems(await api.blockedList()); } catch {} }, []);
  useEffect(() => { load(); }, [load]);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.background }} edges={["top"]}>
      <View style={[styles.header, { borderBottomColor: c.border }]}>
        <TouchableOpacity onPress={() => router.back()}><Ionicons name="chevron-back" size={26} color={c.textPrimary} /></TouchableOpacity>
        <Text variant="h3" style={{ flex: 1, marginLeft: 8 }}>Blocked contacts</Text>
      </View>
      <FlatList
        data={items}
        keyExtractor={(it) => it.id}
        contentContainerStyle={{ padding: 16 }}
        renderItem={({ item }) => (
          <View style={[styles.row, { backgroundColor: c.surface, borderColor: c.border }]}>
            <Avatar name={item.display_name} uri={item.avatar} size={44} />
            <Text style={{ flex: 1, marginLeft: 12, fontWeight: "600" }}>{item.display_name}</Text>
            <TouchableOpacity onPress={async () => { await api.unblock(item.id); load(); }}>
              <Text color={c.primary} style={{ fontWeight: "700" }}>Unblock</Text>
            </TouchableOpacity>
          </View>
        )}
        ListEmptyComponent={<Text color={c.textTertiary} style={{ textAlign: "center", marginTop: 60 }}>You haven&apos;t blocked anyone.</Text>}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "center", padding: 14, gap: 8, borderBottomWidth: StyleSheet.hairlineWidth },
  row: { flexDirection: "row", alignItems: "center", padding: 12, borderRadius: 14, borderWidth: 1, marginBottom: 10 },
});
