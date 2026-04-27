import React, { createContext, useContext, useMemo, useState, useCallback } from "react";
import { useColorScheme } from "react-native";

export type ThemeMode = "light" | "dark" | "system";

export const palette = {
  light: {
    background: "#F8F9FC",
    surface: "#FFFFFF",
    surfaceVariant: "#F1F5F9",
    primary: "#4F46E5",
    primaryDeep: "#3730A3",
    secondary: "#8B5CF6",
    gradient: ["#4F46E5", "#8B5CF6"] as const,
    textPrimary: "#0F172A",
    textSecondary: "#64748B",
    textTertiary: "#94A3B8",
    border: "#E2E8F0",
    success: "#10B981",
    error: "#EF4444",
    warning: "#F59E0B",
    bubbleSent: "#4F46E5",
    bubbleReceived: "#F1F5F9",
    bubbleTextSent: "#FFFFFF",
    bubbleTextReceived: "#0F172A",
    overlay: "rgba(15, 23, 42, 0.5)",
  },
  dark: {
    background: "#0A0B10",
    surface: "#12141D",
    surfaceVariant: "#1E202B",
    primary: "#6366F1",
    primaryDeep: "#4338CA",
    secondary: "#A78BFA",
    gradient: ["#6366F1", "#A78BFA"] as const,
    textPrimary: "#F8FAFC",
    textSecondary: "#94A3B8",
    textTertiary: "#64748B",
    border: "#272A37",
    success: "#34D399",
    error: "#F87171",
    warning: "#FBBF24",
    bubbleSent: "#6366F1",
    bubbleReceived: "#1E202B",
    bubbleTextSent: "#FFFFFF",
    bubbleTextReceived: "#F8FAFC",
    overlay: "rgba(0, 0, 0, 0.65)",
  },
};

export const spacing = { xs: 4, sm: 8, md: 16, lg: 24, xl: 32 };
export const radius = { sm: 8, md: 12, lg: 16, xl: 24, full: 9999 };

type ThemeContextValue = {
  mode: ThemeMode;
  isDark: boolean;
  c: typeof palette.light;
  setMode: (m: ThemeMode) => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const sys = useColorScheme();
  const [mode, setMode] = useState<ThemeMode>("dark");
  const isDark = mode === "dark" || (mode === "system" && sys === "dark");
  const c = isDark ? palette.dark : palette.light;
  const setModeCb = useCallback((m: ThemeMode) => setMode(m), []);
  const value = useMemo(() => ({ mode, isDark, c, setMode: setModeCb }), [mode, isDark, c, setModeCb]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
};

function useCallbackSet<T>(fn: React.Dispatch<React.SetStateAction<T>>) {
  return useCallback((v: T) => fn(v), [fn]);
}

export function useTheme() {
  const v = useContext(ThemeContext);
  if (!v) throw new Error("ThemeProvider missing");
  return v;
}
