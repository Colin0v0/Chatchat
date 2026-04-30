import { useCallback, useState } from "react";

import { DesktopSidebar } from "./sidebar/DesktopSidebar";
import { MobileSidebar } from "./sidebar/MobileSidebar";
import { SidebarSearchDialog } from "./sidebar/SidebarSearchDialog";
import type { SidebarProps } from "./sidebar/types";

type SidebarRootProps = Omit<SidebarProps, "onOpenSearch">;

export function Sidebar(props: SidebarRootProps) {
  const [searchOpen, setSearchOpen] = useState(false);
  const handleOpenSearch = useCallback(() => setSearchOpen(true), []);
  const handleCloseSearch = useCallback(() => {
    setSearchOpen(false);
    props.onQueryChange("");
  }, [props.onQueryChange]);

  return (
    <>
      <DesktopSidebar {...props} onOpenSearch={handleOpenSearch} />
      <MobileSidebar {...props} onOpenSearch={handleOpenSearch} />
      <SidebarSearchDialog
        activity={props.activity}
        debateActivity={props.debateActivity}
        debateItems={props.debateItems}
        battleItems={props.battleItems}
        items={props.items}
        onClose={handleCloseSearch}
        onQueryChange={props.onQueryChange}
        onSelect={props.onSelect}
        onSelectDebate={props.onSelectDebate}
        onSelectBattle={props.onSelectBattle}
        open={searchOpen}
        query={props.query}
      />
    </>
  );
}
