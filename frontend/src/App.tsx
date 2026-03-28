import { useChatApp } from "./app/useChatApp";
import { useResponsiveSidebar } from "./app/useResponsiveSidebar";
import { ConversationView } from "./components/ConversationView";
import { LandingView } from "./components/LandingView";
import { MainHeader } from "./components/MainHeader";
import { SettingsDialog } from "./components/SettingsDialog";
import { Sidebar } from "./components/Sidebar";

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
      Chatchat can make mistakes. Please verify important information.
    </div>
  );
}

export default function App() {
  const sidebar = useResponsiveSidebar();
  const app = useChatApp({
    closeMobileSidebar: sidebar.closeMobileSidebar,
    isDesktop: sidebar.isDesktop,
    sidebarOpen: sidebar.sidebarOpen,
    toggleSidebar: sidebar.toggleSidebar,
  });

  return (
    <div className="flex h-[100dvh] min-h-0 overflow-hidden bg-app-bg text-app-text">
      <Sidebar {...app.sidebarProps} />

      <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-app-panel">
        <MainHeader {...app.headerProps} />

        {app.showLanding || !app.conversationProps ? (
          <LandingView {...app.landingProps} />
        ) : (
          <ConversationView {...app.conversationProps} />
        )}

        <ErrorToast message={app.error} />
        <Disclaimer />
      </main>

      <SettingsDialog {...app.settingsProps} />
    </div>
  );
}
