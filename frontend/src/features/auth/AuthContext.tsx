import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import {
  apiClient,
  setAccessToken,
  type LoginRequest,
  type PinLoginRequest,
  type UserRole,
  type UserSummary,
} from "@/services/api";

interface AuthContextValue {
  user: UserSummary | null;
  isAuthenticated: boolean;
  isBootstrapping: boolean;
  loginWithPassword: (payload: LoginRequest) => Promise<UserSummary>;
  loginWithPin: (payload: PinLoginRequest) => Promise<UserSummary>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function getDefaultRouteForRole(role: UserRole): string {
  switch (role) {
    case "FARMER":
      return "/farmer";
    case "BUYER":
      return "/buyer";
    case "OPERATOR":
      return "/operator";
    case "ADMIN":
      return "/admin";
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserSummary | null>(null);
  const [isBootstrapping, setIsBootstrapping] = useState(true);

  useEffect(() => {
    let active = true;
    const bootstrap = async () => {
      try {
        const res = await apiClient.refresh();
        if (active) {
          setUser(res.user);
        }
      } catch {
        if (active) {
          setAccessToken(null);
          setUser(null);
        }
      } finally {
        if (active) {
          setIsBootstrapping(false);
        }
      }
    };
    void bootstrap();
    return () => {
      active = false;
    };
  }, []);

  const loginWithPassword = async (payload: LoginRequest): Promise<UserSummary> => {
    const res = await apiClient.login(payload);
    setUser(res.user);
    return res.user;
  };

  const loginWithPin = async (payload: PinLoginRequest): Promise<UserSummary> => {
    const res = await apiClient.pinLogin(payload);
    setUser(res.user);
    return res.user;
  };

  const logout = async (): Promise<void> => {
    await apiClient.logout();
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: user !== null,
        isBootstrapping,
        loginWithPassword,
        loginWithPin,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}

