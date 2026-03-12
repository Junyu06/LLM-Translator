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
    <main className="shell app-shell">
      <header className="masthead shell-header">
        {topBar}
        {statusBar}
      </header>

      <section className={`workspace shell-body ${contextPanel ? "has-context-panel" : ""}`}>
        {sidebar}
        <div className="main-stage shell-main">{children}</div>
        {contextPanel}
      </section>
    </main>
  );
}
