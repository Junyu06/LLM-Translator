import type { ReactNode } from "react";

type AppShellProps = {
  topBar: ReactNode;
  statusBar: ReactNode;
  children: ReactNode;
};

export function AppShell({ topBar, statusBar, children }: AppShellProps) {
  return (
    <main className="shell">
      <header className="masthead">
        {topBar}
        {statusBar}
      </header>

      <section className="workspace">{children}</section>
    </main>
  );
}
