import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api, getToken, saveToken, clearToken } from "./api";

type User = {
  id: string;
  email: string;
  display_name: string;
  avatar?: string | null;
  bio?: string;
  status?: string;
  online?: boolean;
  last_seen?: string;
};

type AuthCtx = {
  user: User | null | undefined; // undefined = loading
  verifyOtp: (email: string, otp: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshMe: () => Promise<void>;
};

const Ctx = createContext<AuthCtx | null>(null);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null | undefined>(undefined);

  const refreshMe = useCallback(async () => {
    try {
      const token = await getToken();
      if (!token) {
        setUser(null);
        return;
      }
      const me = await api.me();
      setUser(me);
    } catch {
      await clearToken();
      setUser(null);
    }
  }, []);

  useEffect(() => {
    refreshMe();
  }, [refreshMe]);

  const verifyOtp = useCallback(async (email: string, otp: string) => {
    const res = await api.verifyOtp(email, otp);
    if (res?.access_token) await saveToken(res.access_token);
    setUser(res.user);
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {}
    await clearToken();
    setUser(null);
  }, []);

  return <Ctx.Provider value={{ user, verifyOtp, logout, refreshMe }}>{children}</Ctx.Provider>;
};

export function useAuth() {
  const v = useContext(Ctx);
  if (!v) throw new Error("AuthProvider missing");
  return v;
}
