import React from "react";
import { View, StyleSheet, Image } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import { Text } from "../../src/components/Text";
import { useTheme } from "../../src/lib/theme";

export default function Calls() {
  const { c } = useTheme();
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.background }} edges={["top"]}>
      <View style={{ paddingHorizontal: 20, paddingTop: 12 }}>
        <Text variant="h2">Calls</Text>
        <Text color={c.textTertiary} variant="small">Voice & video — coming soon</Text>
      </View>
      <View style={styles.empty}>
        <LinearGradient colors={c.gradient as any} style={styles.iconWrap}>
          <Ionicons name="call" size={42} color="#fff" />
        </LinearGradient>
        <Text variant="h3" style={{ marginTop: 24 }} testID="calls-empty-title">Calls are on the way</Text>
        <Text color={c.textSecondary} style={{ textAlign: "center", marginTop: 10, paddingHorizontal: 36, lineHeight: 22 }}>
          One-tap voice and video calls with crystal-clear quality will land here in the next update. Until then, share a voice note in chat — it&apos;s the next best thing.
        </Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  empty: { flex: 1, alignItems: "center", justifyContent: "center", paddingBottom: 80 },
  iconWrap: { width: 96, height: 96, borderRadius: 28, alignItems: "center", justifyContent: "center" },
});
