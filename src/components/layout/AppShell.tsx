import type { ReactNode } from "react";

type AppShellProps = {
  topBar: ReactNode;
  sidebar?: ReactNode;
  statusBar: ReactNode;
  children: ReactNode;
};

export function AppShell({ topBar, sidebar, statusBar, children }: AppShellProps) {
  return (
    <main className="shell">
      <header className="masthead">
        {topBar}
        {statusBar}
      </header>

      <section className="workspace">
        {sidebar}
        {children}
      </section>
    </main>
  );
}
