import { createContext, useContext, useState, useCallback, useEffect, ReactNode } from 'react';
import { RelayEnvironmentProvider } from 'react-relay';
import { relayEnvironment, resetRelayEnvironment } from '@/api/relayEnvironment';

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  currentUserId: number | null;
  login: (credentials: { email: string; password: string }) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [currentUserId, setCurrentUserId] = useState<number | null>(null);
  const [environment, setEnvironment] = useState(() => relayEnvironment);

  // Check for existing token on mount
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    const userId = localStorage.getItem('user_id');
    if (token) {
      setIsAuthenticated(true);
      setCurrentUserId(userId ? parseInt(userId, 10) : null);
    }
    setIsLoading(false);
  }, []);

  const login = useCallback(async (credentials: { email: string; password: string }) => {
    const response = await fetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(credentials),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: '로그인에 실패했습니다.' }));
      throw new Error(error.message || '아이디 또는 비밀번호가 올바르지 않습니다');
    }

    const data = await response.json();
    localStorage.setItem('access_token', data.accessToken);
    localStorage.setItem('refresh_token', data.refreshToken);
    localStorage.setItem('user_id', String(data.userId));

    // Reset Relay environment to clear any cached data from previous user
    const newEnv = resetRelayEnvironment();
    setEnvironment(newEnv);
    setCurrentUserId(data.userId);
    setIsAuthenticated(true);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user_id');
    setCurrentUserId(null);
    setIsAuthenticated(false);

    // Reset Relay environment
    const newEnv = resetRelayEnvironment();
    setEnvironment(newEnv);
  }, []);

  return (
    <AuthContext.Provider value={{ isAuthenticated, isLoading, currentUserId, login, logout }}>
      <RelayEnvironmentProvider environment={environment}>
        {children}
      </RelayEnvironmentProvider>
    </AuthContext.Provider>
  );
}
