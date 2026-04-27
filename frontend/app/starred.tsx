import React, { useEffect, useState } from "react";
import { View, StyleSheet, FlatList, TouchableOpacity } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { Text } from "../src/components/Text";
import { useTheme } from "../src/lib/theme";
import { api } from "../src/lib/api";

export default function Starred() {
  const { c } = useTheme();
  const router = useRouter();
  const [items, setItems] = useState<any[]>([]);
  useEffect(() => { api.starred().then(setItems).catch(() => {}); }, []);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.background }} edges={["top"]}>
      <View style={[styles.header, { borderBottomColor: c.border }]}>
        <TouchableOpacity onPress={() => router.back()}><Ionicons name="chevron-back" size={26} color={c.textPrimary} /></TouchableOpacity>
        <Text variant="h3" style={{ flex: 1, marginLeft: 8 }}>Starred messages</Text>
      </View>
      <FlatList
        data={items}
        keyExtractor={(it) => it.id}
        contentContainerStyle={{ padding: 16 }}
        renderItem={({ item }) => (
          <TouchableOpacity onPress={() => router.push({ pathname: "/chat/[id]", params: { id: item.conversation_id } })} style={[styles.row, { backgroundColor: c.surface, borderColor: c.border }]}>
            <Ionicons name="star" size={16} color={c.warning} />
            <View style={{ flex: 1 }}>
              <Text variant="small" color={c.textTertiary}>{item.sender_name}</Text>
              <Text numberOfLines={2}>{item.type === "text" ? item.content : `[${item.type}]`}</Text>
            </View>
          </TouchableOpacity>
        )}
        ListEmptyComponent={<Text color={c.textTertiary} style={{ textAlign: "center", marginTop: 60 }}>No starred messages yet. Long-press a message to star it.</Text>}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "center", padding: 14, gap: 8, borderBottomWidth: StyleSheet.hairlineWidth },
  row: { flexDirection: "row", alignItems: "flex-start", gap: 10, padding: 14, borderRadius: 14, borderWidth: 1, marginBottom: 10 },
});
