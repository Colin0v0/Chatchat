import { useCallback, useEffect, useState } from "react";

import { ApiError } from "../../../shared/api/http";
import { useLatestRequestGuard } from "../../../shared/hooks/useLatestRequestGuard";
import type { AuthUser } from "../../../types";
import { fetchSession, login, logout } from "../api/session";

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

const SESSION_BOOTSTRAP_TIMEOUT_MS = 8000;

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

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function createBootstrapTimeoutError(): LoginErrorState {
  return {
    ...EMPTY_LOGIN_ERROR,
    form: "连接后端超时。请确认后端服务已启动，再刷新页面。",
  };
}

function createBootstrapNetworkError(): LoginErrorState {
  return {
    ...EMPTY_LOGIN_ERROR,
    form: "无法连接后端服务。请确认后端 8050 端口正常运行后重试。",
  };
}

export function useAuthSession() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isBootstrapping, setIsBootstrapping] = useState(true);
  const [authError, setAuthError] = useState<LoginErrorState>(EMPTY_LOGIN_ERROR);
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const bootstrapGuard = useLatestRequestGuard();

  const refreshSession = useCallback(async () => {
    const requestId = bootstrapGuard.begin();
    setIsBootstrapping(true);
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), SESSION_BOOTSTRAP_TIMEOUT_MS);
    try {
      const session = await fetchSession({ signal: controller.signal });
      if (!bootstrapGuard.isCurrent(requestId)) {
        return;
      }
      setUser(session.user);
      setAuthError(EMPTY_LOGIN_ERROR);
    } catch (error) {
      if (!bootstrapGuard.isCurrent(requestId)) {
        return;
      }
      if (!(error instanceof ApiError && error.status === 401)) {
        console.warn("Failed to restore session.", error);
      }
      setUser(null);
      if (isAbortError(error)) {
        setAuthError(createBootstrapTimeoutError());
      } else if (error instanceof TypeError) {
        setAuthError(createBootstrapNetworkError());
      } else {
        setAuthError(EMPTY_LOGIN_ERROR);
      }
    } finally {
      window.clearTimeout(timeoutId);
      if (bootstrapGuard.isCurrent(requestId)) {
        setIsBootstrapping(false);
      }
    }
  }, [bootstrapGuard]);

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
