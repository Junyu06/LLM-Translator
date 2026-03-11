type AppView = "work" | "home" | "history" | "resources" | "settings";

type SidebarItem = {
  id: AppView;
  label: string;
};

type SidebarProps = {
  activeView: AppView;
  onSelect: (view: AppView) => void;
};

const items: SidebarItem[] = [
  { id: "home", label: "Home" },
  { id: "work", label: "Work" },
  { id: "history", label: "History" },
  { id: "resources", label: "Resources" },
  { id: "settings", label: "Settings" }
];

export function Sidebar({ activeView, onSelect }: SidebarProps) {
  return (
    <aside className="sidebar panel">
      <div className="sidebar-header">
        <p className="section-kicker">Navigation</p>
        <h2>Workspace</h2>
      </div>

      <nav className="sidebar-nav" aria-label="Primary">
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`sidebar-link ${item.id === activeView ? "active" : ""}`}
            onClick={() => onSelect(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>
    </aside>
  );
}

export type { AppView };
