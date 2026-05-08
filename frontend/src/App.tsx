import { useCallback, useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";

import { useChatApp } from "./features/workspace/model/useChatApp";
import { useResponsiveSidebar } from "./features/workspace/model/useResponsiveSidebar";
import { MainHeader } from "./features/workspace/ui/MainHeader";
import { PetLayer } from "./features/pet/ui/PetLayer";
import { usePetPreferences } from "./features/pet/model/usePetPreferences";
import { Sidebar } from "./features/workspace/ui/Sidebar";
import { WorkspaceMainView } from "./features/workspace/ui/WorkspaceMainView";
import type { WorkspaceSection } from "./features/workspace/model/workspaceSections";
import { useAuthSession } from "./features/auth/model/useAuthSession";
import { LoginView } from "./features/auth/ui/LoginView";
import { SettingsDialog } from "./features/settings/ui/SettingsDialog";
import { setUnauthorizedHandler } from "./shared/api/http";
import { LoaderCircle } from "lucide-react";

type RoutableWorkspaceSection = Exclude<WorkspaceSection, "debates">;

const WORKSPACE_SECTION_PATHS: Record<RoutableWorkspaceSection, string> = {
  battle: "/battle",
  chats: "/",
  knowledge: "/knowledge",
  memories: "/memories",
  models: "/models",
};

function isRoutableSection(section: WorkspaceSection): section is RoutableWorkspaceSection {
  return section !== "debates";
}

function sectionFromPathname(pathname: string): WorkspaceSection | null {
  if (pathname === "/" || pathname === "/chats") {
    return "chats";
  }

  const match = (Object.entries(WORKSPACE_SECTION_PATHS) as Array<[RoutableWorkspaceSection, string]>).find(
    ([section, path]) => section !== "chats" && pathname === path,
  );
  return match?.[0] ?? null;
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
  userId,
}: {
  onLogout: () => void;
  username: string;
  userId: number | null;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const sidebar = useResponsiveSidebar();
  const petPreferences = usePetPreferences();
  const routeSection = sectionFromPathname(location.pathname) ?? "chats";
  const routeKnown = sectionFromPathname(location.pathname) !== null;
  const handleSectionRouteChange = useCallback(
    (section: WorkspaceSection) => {
      if (!isRoutableSection(section)) {
        return;
      }
      const nextPath = WORKSPACE_SECTION_PATHS[section];
      if (location.pathname !== nextPath) {
        navigate(nextPath);
      }
    },
    [location.pathname, navigate],
  );
  const app = useChatApp({
    closeMobileSidebar: sidebar.closeMobileSidebar,
    isDesktop: sidebar.isDesktop,
    onSectionRouteChange: handleSectionRouteChange,
    routeSection,
    sidebarOpen: sidebar.sidebarOpen,
    toggleSidebar: sidebar.toggleSidebar,
    userId,
  });

  useEffect(() => {
    if (!routeKnown) {
      navigate("/", { replace: true });
    }
  }, [navigate, routeKnown]);

  return (
    <div className="flex h-[100dvh] min-h-0 overflow-hidden bg-app-bg text-app-text">
      <Sidebar
        {...app.sidebarProps}
        onLogout={onLogout}
        onOpenSettings={() => {
          sidebar.closeMobileSidebar();
          setSettingsOpen(true);
        }}
        settingsActive={settingsOpen}
        viewerName={username}
      />

      <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-app-panel">
        <MainHeader {...app.headerProps} />
        <WorkspaceMainView
          activeSection={app.activeSection}
          battlePageProps={app.battlePageProps}
          conversationProps={app.conversationProps}
          debateCreateProps={app.debateCreateProps}
          debateRoomProps={app.debateRoomProps}
          isBattleLoading={app.isBattleLoading}
          isConversationLoading={app.isConversationLoading}
          isDebateLoading={app.isDebateLoading}
          knowledgePageProps={app.knowledgePageProps}
          landingProps={app.landingProps}
          memoriesPageProps={app.memoriesPageProps}
          modelsPageProps={app.modelsPageProps}
          showLanding={app.showLanding}
        />

        <ErrorToast message={app.error} />
        {petPreferences.preferences.enabled ? (
          <PetLayer
            activitySignal={app.petActivity.signal}
            activeSection={app.activeSection}
            context={app.petActivity.context}
            draftActive={app.petActivity.draftActive}
            isStreaming={app.petActivity.isStreaming}
            preferences={petPreferences.preferences}
            sidebarOpen={sidebar.sidebarOpen}
          />
        ) : null}
        {(app.activeSection !== "debates" || !app.debateRoomProps) ? <Disclaimer /> : null}
      </main>

      <SettingsDialog
        {...app.imageSettingsProps}
        onClose={() => setSettingsOpen(false)}
        onPetEnabledChange={petPreferences.setEnabled}
        onPetPreferencesChange={petPreferences.updatePreferences}
        open={settingsOpen}
        petEnabled={petPreferences.preferences.enabled}
        petPreferences={petPreferences.preferences}
        username={username}
      />
    </div>
  );
}

export default function App() {
  const navigate = useNavigate();
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
    setUnauthorizedHandler(() => {
      clearSession();
      navigate("/login", { replace: true });
    });

    return () => setUnauthorizedHandler(null);
  }, [clearSession, navigate]);

  const handleLogin = useCallback(
    async (username: string, password: string) => {
      const nextUser = await signIn(username, password);
      if (nextUser) {
        navigate("/", { replace: true });
      }
    },
    [navigate, signIn],
  );

  const handleLogout = useCallback(() => {
    void signOut();
    navigate("/login", { replace: true });
  }, [navigate, signOut]);

  if (isBootstrapping) {
    return (
      <section className="flex min-h-[100dvh] items-center justify-center bg-app-bg px-6">
        <div className="flex flex-col items-center gap-4 text-center text-app-muted">
          <LoaderCircle className="size-8 animate-spin text-app-muted" />
        </div>
      </section>
    );
  }

  if (!user) {
    return (
      <Routes>
        <Route
          element={
            <LoginView
              error={authError}
              isSubmitting={isLoggingIn || isLoggingOut}
              onClearError={clearAuthError}
              onSubmit={handleLogin}
            />
          }
          path="/login"
        />
        <Route element={<Navigate replace to="/login" />} path="*" />
      </Routes>
    );
  }

  return (
    <Routes>
      <Route element={<Navigate replace to="/" />} path="/login" />
      <Route element={<WorkspaceApp onLogout={handleLogout} username={user.username} userId={user.id} />} path="/*" />
    </Routes>
  );
}
