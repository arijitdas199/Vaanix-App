import React from "react";
import { View, StyleSheet, Image } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Text } from "./Text";
import { useTheme } from "../lib/theme";

const GRADIENTS = [
  ["#4F46E5", "#8B5CF6"],
  ["#06B6D4", "#3B82F6"],
  ["#F59E0B", "#EF4444"],
  ["#10B981", "#22D3EE"],
  ["#8B5CF6", "#EC4899"],
  ["#0EA5E9", "#6366F1"],
] as const;

function pickGradient(seed: string): readonly [string, string] {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) | 0;
  return GRADIENTS[Math.abs(h) % GRADIENTS.length];
}

function initials(name: string): string {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] || "") + (parts[1]?.[0] || "")).toUpperCase() || "?";
}

export const Avatar: React.FC<{
  name?: string;
  uri?: string | null;
  size?: number;
  online?: boolean;
}> = ({ name = "", uri, size = 48, online }) => {
  const { c } = useTheme();
  const grad = pickGradient(name || uri || "x");
  const fontSize = Math.max(11, Math.round(size * 0.38));
  return (
    <View style={{ width: size, height: size }}>
      {uri ? (
        <Image source={{ uri }} style={{ width: size, height: size, borderRadius: size / 2 }} />
      ) : (
        <LinearGradient
          colors={grad as any}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={{ width: size, height: size, borderRadius: size / 2, alignItems: "center", justifyContent: "center" }}
        >
          <Text style={{ color: "#fff", fontWeight: "700", fontSize }}>{initials(name)}</Text>
        </LinearGradient>
      )}
      {online ? (
        <View
          style={[
            styles.dot,
            { backgroundColor: c.success, borderColor: c.surface, width: size * 0.28, height: size * 0.28, borderRadius: size * 0.14 },
          ]}
        />
      ) : null}
    </View>
  );
};

const styles = StyleSheet.create({
  dot: {
    position: "absolute",
    bottom: 0,
    right: 0,
    borderWidth: 2,
  },
});
