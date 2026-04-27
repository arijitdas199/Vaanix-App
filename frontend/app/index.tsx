import React, { useEffect } from "react";
import { View, ActivityIndicator, StyleSheet, Image } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { useRouter } from "expo-router";
import { useAuth } from "../src/lib/auth";
import { useTheme } from "../src/lib/theme";
import { Text } from "../src/components/Text";

export default function Index() {
  const { user } = useAuth();
  const { c } = useTheme();
  const router = useRouter();

  useEffect(() => {
    if (user === undefined) return;
    if (user) router.replace("/(tabs)/chats");
    else router.replace("/(auth)/welcome");
  }, [user, router]);

  return (
    <LinearGradient colors={["#0A0B10", "#1E1B4B", "#312E81"]} style={styles.container}>
      <View style={styles.iconWrap}>
        <Image source={require("../assets/images/vaanix-logo.png")} style={styles.logo} resizeMode="cover" />
      </View>
      <Text variant="h1" color="#fff" style={{ marginTop: 12 }} testID="splash-title">Vaanix</Text>
      <Text color="#A78BFA" style={{ marginTop: 6 }}>Connect Beyond Words</Text>
      <ActivityIndicator color="#A78BFA" style={{ marginTop: 28 }} />
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: "center", justifyContent: "center" },
  iconWrap: { shadowColor: "#A78BFA", shadowOpacity: 0.55, shadowRadius: 28, shadowOffset: { width: 0, height: 14 }, elevation: 24 },
  logo: { width: 120, height: 120, borderRadius: 32 },
});
