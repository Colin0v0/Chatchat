import { useCallback, useEffect, useRef, useState } from "react";

const SIDEBAR_STORAGE_KEY = "chatchat:sidebar-state";

type SidebarState = {
  desktopOpen: boolean;
  mobileOpen: boolean;
};

function isDesktopViewport() {
  if (typeof window === "undefined") {
    return true;
  }

  return window.innerWidth >= 768;
}

function getDefaultSidebarState(): SidebarState {
  return {
    desktopOpen: true,
    mobileOpen: false,
  };
}

function readSidebarState(): SidebarState {
  if (typeof window === "undefined") {
    return getDefaultSidebarState();
  }

  try {
    const raw = window.localStorage.getItem(SIDEBAR_STORAGE_KEY);
    if (!raw) {
      return getDefaultSidebarState();
    }

    const parsed = JSON.parse(raw) as Partial<SidebarState>;
    return {
      desktopOpen: parsed.desktopOpen ?? true,
      mobileOpen: parsed.mobileOpen ?? false,
    };
  } catch {
    return getDefaultSidebarState();
  }
}

function writeSidebarState(state: SidebarState) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(SIDEBAR_STORAGE_KEY, JSON.stringify(state));
}

export function useResponsiveSidebar() {
  const [sidebarState, setSidebarState] = useState<SidebarState>(() => readSidebarState());
  const [isDesktop, setIsDesktop] = useState(() => isDesktopViewport());
  const [sidebarOpen, setSidebarOpen] = useState(() => {
    const desktop = isDesktopViewport();
    const persisted = readSidebarState();
    return desktop ? persisted.desktopOpen : persisted.mobileOpen;
  });
  const lastDesktopRef = useRef(isDesktopViewport());

  useEffect(() => {
    writeSidebarState(sidebarState);
  }, [sidebarState]);

  useEffect(() => {
    function syncViewportState() {
      const desktop = isDesktopViewport();
      setIsDesktop(desktop);
      if (desktop !== lastDesktopRef.current) {
        setSidebarOpen(desktop ? sidebarState.desktopOpen : sidebarState.mobileOpen);
        lastDesktopRef.current = desktop;
      }
    }

    syncViewportState();
    window.addEventListener("resize", syncViewportState);
    return () => window.removeEventListener("resize", syncViewportState);
  }, [sidebarState.desktopOpen, sidebarState.mobileOpen]);

  const setOpen = useCallback(
    (nextOpen: boolean | ((current: boolean) => boolean), desktop = isDesktop) => {
      setSidebarOpen((current) => {
        const resolved = typeof nextOpen === "function" ? nextOpen(current) : nextOpen;
        setSidebarState((previous) =>
          desktop
            ? { ...previous, desktopOpen: resolved }
            : { ...previous, mobileOpen: resolved },
        );
        return resolved;
      });
    },
    [isDesktop],
  );

  const closeMobileSidebar = useCallback(() => {
    setOpen(false, false);
  }, [setOpen]);

  const toggleSidebar = useCallback(() => {
    setOpen((current) => !current);
  }, [setOpen]);

  return {
    closeMobileSidebar,
    isDesktop,
    sidebarOpen,
    toggleSidebar,
  };
}
