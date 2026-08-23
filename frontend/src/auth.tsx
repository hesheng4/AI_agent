// 认证上下文 — 全局管理用户状态与 token
import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { authApi, getToken, setToken, setRefreshToken, clearToken, isTokenExpired } from './api';
import type { User } from './types';

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  setUser: (user: User | null) => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

// 迁移 localStorage → sessionStorage（安全加固）
function migrateToken() {
  try {
    const old = localStorage.getItem('moguan_token');
    if (old) {
      localStorage.removeItem('moguan_token');
      if (!isTokenExpired(old)) {
        setToken(old);
      }
    }
  } catch {}
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    migrateToken();
    const token = getToken();
    if (!token || isTokenExpired(token)) {
      clearToken();
      setLoading(false);
      return;
    }
    authApi
      .me()
      .then(setUser)
      .catch(() => {
        clearToken();
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  async function login(email: string, password: string) {
    const { access_token, refresh_token } = await authApi.login({ email, password });
    setToken(access_token);
    setRefreshToken(refresh_token);
    const me = await authApi.me();
    setUser(me);
  }

  function logout() {
    clearToken();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, setUser }}>
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth 必须在 AuthProvider 内使用');
  return ctx;
}
