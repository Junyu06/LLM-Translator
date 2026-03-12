import type { ReactNode } from "react";

type ContextPanelProps = {
  title: string;
  isOpen: boolean;
  onToggle: () => void;
  children: ReactNode;
};

export function ContextPanel({ title, isOpen, onToggle, children }: ContextPanelProps) {
  if (!isOpen) {
    return (
      <aside className="context-panel-rail shell-context-rail">
        <button className="ghost context-toggle" type="button" onClick={onToggle} aria-expanded={false}>
          Show details
        </button>
      </aside>
    );
  }

  return (
    <aside className="panel context-panel shell-context">
      <div className="context-panel-header">
        <div>
          <p className="section-kicker">Context</p>
          <h2 className="context-panel-title">{title}</h2>
        </div>
        <button className="ghost context-toggle" type="button" onClick={onToggle} aria-expanded={true}>
          Hide details
        </button>
      </div>
      {children}
    </aside>
  );
}
