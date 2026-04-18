import type { ReactNode } from "react";

function WorkspacePageHeader({
  actions,
  subtitle,
  title,
}: {
  actions?: ReactNode;
  subtitle?: string;
  title: string;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0 flex-1">
        <div className="text-[28px] font-semibold tracking-[-0.04em] text-app-text">{title}</div>
        {subtitle ? <div className="mt-2 text-[14px] leading-7 text-app-muted">{subtitle}</div> : null}
      </div>
      {actions ? <div className="flex w-full flex-wrap items-center gap-3 sm:w-auto sm:justify-end">{actions}</div> : null}
    </div>
  );
}

export function WorkspacePage({
  actions,
  children,
  headerPlacement = "section",
  maxWidthClassName = "max-w-[1120px]",
  subtitle,
  title,
}: {
  actions?: ReactNode;
  children: ReactNode;
  headerPlacement?: "section" | "content";
  maxWidthClassName?: string;
  subtitle?: string;
  title: string;
}) {
  return (
    <section className="flex min-h-0 flex-1 flex-col">
      {headerPlacement === "section" ? (
        <div className="border-b border-app-border px-4 py-5 md:px-6">
          <div className={["mx-auto w-full", maxWidthClassName].join(" ")}>
            <WorkspacePageHeader actions={actions} subtitle={subtitle} title={title} />
          </div>
        </div>
      ) : null}

      <div className="app-scrollbar min-h-0 flex-1 overflow-y-auto">
        <div className={["mx-auto flex w-full flex-col gap-6 px-4 py-6 md:px-6", maxWidthClassName].join(" ")}>
          {headerPlacement === "content" ? (
            <WorkspacePageHeader actions={actions} subtitle={subtitle} title={title} />
          ) : null}
          {children}
        </div>
      </div>
    </section>
  );
}
