import { useCallback, useEffect, useState } from "react";

import { ApiError, fetchSession, login, logout } from "../lib/api";
import type { AuthUser } from "../types";

export interface LoginErrorState {
  form: string | null;
  password: string | null;
  username: string | null;
}

const EMPTY_LOGIN_ERROR: LoginErrorState = {
  form: null,
  password: null,
  username: null,
};

function toLoginErrorState(error: unknown): LoginErrorState {
  if (error instanceof ApiError) {
    if (error.code === "user_not_found") {
      return { ...EMPTY_LOGIN_ERROR, username: "用户未注册" };
    }
    if (error.code === "invalid_password") {
      return { ...EMPTY_LOGIN_ERROR, password: "密码错误" };
    }
    return { ...EMPTY_LOGIN_ERROR, form: error.message };
  }
  return { ...EMPTY_LOGIN_ERROR, form: "登录失败" };
}

export function useAuthSession() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isBootstrapping, setIsBootstrapping] = useState(true);
  const [authError, setAuthError] = useState<LoginErrorState>(EMPTY_LOGIN_ERROR);
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const refreshSession = useCallback(async () => {
    setIsBootstrapping(true);
    try {
      const session = await fetchSession();
      setUser(session.user);
      setAuthError(EMPTY_LOGIN_ERROR);
    } catch (error) {
      if (!(error instanceof ApiError && error.status === 401)) {
        console.warn("Failed to restore session.", error);
      }
      setUser(null);
      setAuthError(EMPTY_LOGIN_ERROR);
    } finally {
      setIsBootstrapping(false);
    }
  }, []);

  useEffect(() => {
    void refreshSession();
  }, [refreshSession]);

  const signIn = useCallback(async (username: string, password: string) => {
    setIsLoggingIn(true);
    setAuthError(EMPTY_LOGIN_ERROR);
    try {
      const session = await login({ username, password });
      setUser(session.user);
      return session.user;
    } catch (error) {
      setAuthError(toLoginErrorState(error));
      return null;
    } finally {
      setIsLoggingIn(false);
    }
  }, []);

  const signOut = useCallback(async () => {
    setIsLoggingOut(true);
    setAuthError(EMPTY_LOGIN_ERROR);
    try {
      await logout();
    } catch (error) {
      console.warn("Logout failed.", error);
    } finally {
      setUser(null);
      setIsLoggingOut(false);
    }
  }, []);

  const clearAuthError = useCallback(() => {
    setAuthError(EMPTY_LOGIN_ERROR);
  }, []);

  const clearSession = useCallback(() => {
    setUser(null);
    setIsBootstrapping(false);
    setAuthError(EMPTY_LOGIN_ERROR);
  }, []);

  return {
    authError,
    clearAuthError,
    clearSession,
    isBootstrapping,
    isLoggingIn,
    isLoggingOut,
    refreshSession,
    signIn,
    signOut,
    user,
  };
}
