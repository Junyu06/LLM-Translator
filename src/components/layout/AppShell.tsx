import type { ReactNode } from "react";

type AppShellProps = {
  topBar: ReactNode;
  sidebar?: ReactNode;
  statusBar: ReactNode;
  contextPanel?: ReactNode;
  children: ReactNode;
};

export function AppShell({ topBar, sidebar, statusBar, contextPanel, children }: AppShellProps) {
  return (
    <div className="app-shell">
      <header className="shell-header">
        {topBar}
        {statusBar}
      </header>

      <div className="shell-body">
        {sidebar}
        <main className="shell-main">
          {children}
        </main>
        {contextPanel && <aside className="shell-context">{contextPanel}</aside>}
      </div>
    </div>
  );
}
