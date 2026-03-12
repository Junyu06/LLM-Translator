import type { ReactNode } from "react";

type TopBarProps = {
  eyebrow: string;
  title: string;
  actions?: ReactNode;
  children?: ReactNode;
};

export function TopBar({ eyebrow, title, actions, children }: TopBarProps) {
  return (
    <div className="title-block topbar">
      <div className="topbar-heading">
        <div className="topbar-copy">
          <p className="eyebrow">{eyebrow}</p>
          <h1 className="topbar-title">{title}</h1>
        </div>
        {actions}
      </div>
      {children}
    </div>
  );
}
