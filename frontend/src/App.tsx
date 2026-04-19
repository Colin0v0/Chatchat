import { useCallback, useEffect, useState } from "react";

import { useChatApp } from "./features/workspace/model/useChatApp";
import { useResponsiveSidebar } from "./features/workspace/model/useResponsiveSidebar";
import { MainHeader } from "./features/workspace/ui/MainHeader";
import { Sidebar } from "./features/workspace/ui/Sidebar";
import { WorkspaceMainView } from "./features/workspace/ui/WorkspaceMainView";
import { useAuthSession } from "./features/auth/model/useAuthSession";
import { LoginView } from "./features/auth/ui/LoginView";
import { setUnauthorizedHandler } from "./shared/api/http";
import { LoaderCircle } from "lucide-react";

type AppRoute = "/" | "/login";

function normalizeRoute(pathname: string): AppRoute {
  return pathname === "/login" ? "/login" : "/";
}

function navigate(path: AppRoute, replace = false) {
  const nextUrl = `${path}${window.location.search}${window.location.hash}`;
  const currentUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  if (nextUrl === currentUrl) {
    return;
  }

  if (replace) {
    window.history.replaceState(null, "", nextUrl);
  } else {
    window.history.pushState(null, "", nextUrl);
  }
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function ErrorToast({ message }: { message: string | null }) {
  if (!message) {
    return null;
  }

  return (
    <div className="fixed top-4 right-4 z-30 max-w-[420px] rounded-lg border border-black/10 bg-app-danger px-4 py-3 text-[14px] text-white md:top-6 md:right-6">
      {message}
    </div>
  );
}

function Disclaimer() {
  return (
    <div className="pointer-events-none px-4 pt-2 pb-2 text-center text-[13px] text-app-muted/80 md:px-6 md:pt-2 md:pb-2">
      <span className="md:hidden">Chatchat can make mistakes.</span>
      <span className="hidden md:inline">Chatchat can make mistakes. Please verify important information.</span>
    </div>
  );
}

function WorkspaceApp({
  onLogout,
  username,
}: {
  onLogout: () => void;
  username: string;
}) {
  const sidebar = useResponsiveSidebar();
  const app = useChatApp({
    closeMobileSidebar: sidebar.closeMobileSidebar,
    isDesktop: sidebar.isDesktop,
    sidebarOpen: sidebar.sidebarOpen,
    toggleSidebar: sidebar.toggleSidebar,
  });

  return (
    <div className="flex h-[100dvh] min-h-0 overflow-hidden bg-app-bg text-app-text">
      <Sidebar {...app.sidebarProps} onLogout={onLogout} viewerName={username} />

      <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-app-panel">
        <MainHeader {...app.headerProps} />
        <WorkspaceMainView
          activeSection={app.activeSection}
          conversationProps={app.conversationProps}
          debateCreateProps={app.debateCreateProps}
          debateRoomProps={app.debateRoomProps}
          isConversationLoading={app.isConversationLoading}
          isDebateLoading={app.isDebateLoading}
          knowledgePageProps={app.knowledgePageProps}
          landingProps={app.landingProps}
          memoriesPageProps={app.memoriesPageProps}
          modelsPageProps={app.modelsPageProps}
          onNewDebate={app.headerProps.onNewDebate}
          showLanding={app.showLanding}
        />

        <ErrorToast message={app.error} />
        {app.activeSection !== "debates" || !app.debateRoomProps ? <Disclaimer /> : null}
      </main>
    </div>
  );
}

export default function App() {
  const [route, setRoute] = useState<AppRoute>(() => normalizeRoute(window.location.pathname));
  const {
    authError,
    clearAuthError,
    clearSession,
    isBootstrapping,
    isLoggingIn,
    isLoggingOut,
    signIn,
    signOut,
    user,
  } = useAuthSession();

  useEffect(() => {
    function handleRouteChange() {
      setRoute(normalizeRoute(window.location.pathname));
    }

    window.addEventListener("popstate", handleRouteChange);
    return () => window.removeEventListener("popstate", handleRouteChange);
  }, []);

  useEffect(() => {
    const normalizedPath = normalizeRoute(window.location.pathname);
    if (window.location.pathname !== normalizedPath) {
      navigate(normalizedPath, true);
    }
  }, [route]);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      clearSession();
      navigate("/login", true);
    });

    return () => setUnauthorizedHandler(null);
  }, [clearSession]);

  useEffect(() => {
    if (isBootstrapping) {
      return;
    }

    if (user) {
      if (route === "/login") {
        navigate("/", true);
      }
      return;
    }

    if (route !== "/login") {
      navigate("/login", true);
    }
  }, [isBootstrapping, route, user]);

  const handleLogin = useCallback(
    async (username: string, password: string) => {
      const nextUser = await signIn(username, password);
      if (nextUser) {
        navigate("/", true);
      }
    },
    [signIn],
  );

  const handleLogout = useCallback(() => {
    void signOut();
    navigate("/login", true);
  }, [signOut]);

  if (isBootstrapping) {
    return (
      <section className="flex min-h-[100dvh] items-center justify-center bg-app-bg px-6">
        <div className="flex flex-col items-center gap-4 text-center text-app-muted">
          <LoaderCircle className="size-8 animate-spin text-app-muted" />
          <p className="text-[14px]">正在连接服务...</p>
        </div>
      </section>
    );
  }

  if (!user) {
    return (
      <LoginView
        error={authError}
        isSubmitting={isLoggingIn || isLoggingOut}
        onClearError={clearAuthError}
        onSubmit={handleLogin}
      />
    );
  }

  return <WorkspaceApp onLogout={handleLogout} username={user.username} />;
}
