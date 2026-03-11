import type { ReactNode } from "react";

type TopBarProps = {
  eyebrow: string;
  title: string;
  children?: ReactNode;
};

export function TopBar({ eyebrow, title, children }: TopBarProps) {
  return (
    <div className="title-block">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
      </div>
      {children}
    </div>
  );
}
