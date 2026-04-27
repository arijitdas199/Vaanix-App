import React from "react";
import { Text as RNText, TextProps, StyleSheet } from "react-native";
import { useTheme } from "../lib/theme";

export const Text: React.FC<TextProps & { variant?: "h1" | "h2" | "h3" | "body" | "small" | "caption"; color?: string }> = ({
  variant = "body",
  color,
  style,
  ...rest
}) => {
  const { c } = useTheme();
  const styles = StyleSheet.flatten([
    { color: color || c.textPrimary },
    variant === "h1" && { fontSize: 32, fontWeight: "800" as const, letterSpacing: -1 },
    variant === "h2" && { fontSize: 24, fontWeight: "700" as const, letterSpacing: -0.5 },
    variant === "h3" && { fontSize: 20, fontWeight: "600" as const, letterSpacing: -0.3 },
    variant === "body" && { fontSize: 16, fontWeight: "400" as const },
    variant === "small" && { fontSize: 13, fontWeight: "400" as const, color: color || c.textSecondary },
    variant === "caption" && { fontSize: 11, fontWeight: "600" as const, letterSpacing: 0.5, textTransform: "uppercase" as const, color: color || c.textTertiary },
    style,
  ]);
  return <RNText {...rest} style={styles} />;
};

export default Text;
