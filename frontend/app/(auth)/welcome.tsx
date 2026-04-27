import React from "react";
import { View, StyleSheet, TouchableOpacity, Image } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { Text } from "../../src/components/Text";

const HERO = "https://static.prod-images.emergentagent.com/jobs/e14f9429-60ef-4aba-b004-7f450f3decb4/images/9611a38242e8e9e7a823a249442209fa0255cec70cae588645efac2171d269a6.png";

export default function Welcome() {
  const router = useRouter();
  return (
    <LinearGradient colors={["#0A0B10", "#1E1B4B", "#0A0B10"]} style={styles.container}>
      <View style={styles.heroWrap}>
        <Image source={require("../../assets/images/vaanix-logo.png")} style={styles.hero} resizeMode="cover" />
      </View>

      <View style={styles.bottom}>
        <View style={styles.brand}>
          <Image source={require("../../assets/images/vaanix-logo.png")} style={styles.brandMark} resizeMode="cover" />
          <Text variant="h2" color="#fff">Vaanix</Text>
        </View>
        <Text variant="h1" color="#fff" style={{ marginTop: 18 }}>Connect Beyond Words.</Text>
        <Text color="#94A3B8" style={{ marginTop: 10, fontSize: 16, lineHeight: 24 }}>
          Lightning-fast, secure conversations. Voice notes, group chats, reactions and more — wrapped in a beautifully premium experience.
        </Text>

        <TouchableOpacity testID="welcome-cta-login" activeOpacity={0.9} onPress={() => router.push("/(auth)/email")} style={{ marginTop: 28 }}>
          <LinearGradient colors={["#6366F1", "#A78BFA"]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.primary}>
            <Text color="#fff" style={{ fontWeight: "700", fontSize: 16 }}>Continue with email</Text>
          </LinearGradient>
        </TouchableOpacity>

        <Text color="#64748B" variant="small" style={{ textAlign: "center", marginTop: 14 }}>
          Passwordless · Secure 6-digit code via email
        </Text>
      </View>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, paddingHorizontal: 24, paddingTop: 64, paddingBottom: 36 },
  heroWrap: { alignItems: "center", justifyContent: "center", flex: 1 },
  hero: { width: 220, height: 220, borderRadius: 56, shadowColor: "#A78BFA", shadowOpacity: 0.6, shadowRadius: 40, shadowOffset: { width: 0, height: 16 } },
  bottom: { paddingTop: 8 },
  brand: { flexDirection: "row", alignItems: "center", gap: 10 },
  brandMark: { width: 40, height: 40, borderRadius: 12 },
  logoBox: { width: 36, height: 36, borderRadius: 10, alignItems: "center", justifyContent: "center" },
  primary: { paddingVertical: 16, borderRadius: 16, alignItems: "center" },
  secondary: { marginTop: 14, paddingVertical: 14, alignItems: "center" },
});
