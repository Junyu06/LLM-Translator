import type { ReactNode } from "react";

type ContextPanelProps = {
  title: string;
  isOpen: boolean;
  onToggle: () => void;
  children: ReactNode;
};

export function ContextPanel({ title, isOpen, onToggle, children }: ContextPanelProps) {
  if (!isOpen) {
    return null; // The toggle is now in the TopBar
  }

  return (
    <aside className="shell-context">
      <div className="output-header" style={{marginBottom: '20px'}}>
        <div>
          <p className="section-kicker">Context</p>
          <h2 className="section-title" style={{marginBottom: 0}}>{title}</h2>
        </div>
        <button className="ghost" type="button" onClick={onToggle} aria-expanded={true}>
          Hide
        </button>
      </div>
      {children}
    </aside>
  );
}
