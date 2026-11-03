import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";
import type { AuthenticatedClient } from "@/features/auth/AuthProvider";

// Navigation items matching the Academic Wordbank design system
const NAV: readonly { to: string; label: string; icon: ReactNode }[] = [
  {
    to: "/library",
    label: "Library",
    icon: (
      <>
        <path d="M4 19.5V5a1 1 0 0 1 1-1h3v16H5a1 1 0 0 1-1-.5z" />
        <path d="M8 4h4v16H8" />
        <path d="m14 5 3.5-1 3 15.5-3.5 1z" />
      </>
    ),
  },
  {
    to: "/phrasebank",
    label: "Phrasebank",
    icon: (
      <>
        <path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H20v14H5.5A1.5 1.5 0 0 0 4 19.5z" />
        <path d="M4 19.5A1.5 1.5 0 0 0 5.5 21H20v-3" />
        <path d="M9 9h7M9 12.5h5" />
      </>
    ),
  },
  {
    to: "/playground",
    label: "Playground",
    icon: (
      <>
        <path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.8 3h10.4a2 2 0 0 0 1.8-3l-5-9V3" />
        <path d="M7.5 15h9" />
      </>
    ),
  },
  {
    to: "/writer",
    label: "Writer",
    icon: (
      <>
        <path d="M12 20h9" />
        <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" />
      </>
    ),
  },
  {
    to: "/inbox",
    label: "Inbox",
    icon: (
      <>
        <path d="M22 12h-6l-2 3h-4l-2-3H2" />
        <path d="M5.5 5h13L22 12v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-6z" />
      </>
    ),
  },
  {
    to: "/journals",
    label: "Journals",
    icon: (
      <>
        <rect x="5" y="3" width="14" height="18" rx="2" />
        <path d="M9 7h6M9 11h6M9 15h3" />
      </>
    ),
  },
  {
    to: "/admin",
    label: "Admin",
    icon: (
      <>
        <path d="M12 3 4 6v6c0 4.5 3.4 8.2 8 9 4.6-.8 8-4.5 8-9V6z" />
        <path d="m9 12 2 2 4-4" />
      </>
    ),
  },
  {
    to: "/import",
    label: "Import",
    icon: (
      <>
        <path d="M12 3v12" />
        <path d="m7 10 5 5 5-5" />
        <path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
      </>
    ),
  },
  {
    to: "/extract",
    label: "Extract",
    icon: (
      <>
        <path d="M4 6h16M4 12h10M4 18h6" />
        <circle cx="17.5" cy="16.5" r="3" />
        <path d="m20 19 2 2" />
      </>
    ),
  },
  {
    to: "/gold",
    label: "Gold review",
    icon: (
      <>
        <circle cx="12" cy="9" r="6" />
        <path d="M8.5 14 7 21l5-3 5 3-1.5-7" />
      </>
    ),
  },
  {
    to: "/vocabulary",
    label: "Vocabulary",
    icon: (
      <>
        <path d="M4 20 9 4h1l5 16" />
        <path d="M6.5 14h6" />
        <path d="M16 9h5M16 13h4M16 17h5" />
      </>
    ),
  },
];

type Props = {
  collapsed: boolean;
  mobileOpen: boolean;
  client: AuthenticatedClient | null;
  onLogout: () => void;
  onToggleCollapsed: () => void;
  onCloseMobile: () => void;
  onNavigate: () => void;
};

export function Sidebar({
  collapsed,
  mobileOpen,
  client,
  onLogout,
  onToggleCollapsed,
  onCloseMobile,
  onNavigate,
}: Props) {
  const isAuthed = Boolean(client);
  const isAdmin = client?.role === "admin";
  const items = NAV.filter((n) => n.to === "/writer" || isAuthed).filter(
    (n) => n.to !== "/admin" || isAdmin,
  );

  return (
    <aside
      id="sidebar"
      className="sidebar"
      data-collapsed={collapsed || undefined}
      data-open={mobileOpen || undefined}
      aria-label="Application Sidebar"
    >
      {/* 3. Nút đóng sidebar đem lên góc phải phía trên */}
      <div className="sidebar-top">
        {!collapsed && <span className="sidebar-top-title">Navigation</span>}
        <button
          type="button"
          className="sidebar-close-btn"
          onClick={() => {
            if (mobileOpen) onCloseMobile();
            else onToggleCollapsed();
          }}
          title={mobileOpen ? "Close sidebar" : collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-label={mobileOpen ? "Close sidebar" : collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-controls="sidebar"
          aria-expanded={mobileOpen || !collapsed}
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden
          >
            {mobileOpen ? (
              <path d="M18 6L6 18M6 6l12 12" />
            ) : collapsed ? (
              <>
                <rect x="3" y="4" width="18" height="16" rx="2" />
                <path d="M9 4v16" />
                <path d="m13 15 3-3-3-3" />
              </>
            ) : (
              <>
                <rect x="3" y="4" width="18" height="16" rx="2" />
                <path d="M9 4v16" />
                <path d="m15 9-3 3 3 3" />
              </>
            )}
          </svg>
        </button>
      </div>

      {/* 1. Danh sách menu cuộn dọc, triệt tiêu hoàn toàn scroll ngang */}
      <nav aria-label="Main Navigation" className="sidebar-nav">
        <ul className="side-list">
          {items.map((n) => (
            <li key={n.to}>
              <Link
                to={n.to}
                className="side-link"
                activeProps={{ "aria-current": "page" }}
                title={collapsed ? n.label : undefined}
                onClick={onNavigate}
              >
                <svg
                  className="side-icon"
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden
                >
                  {n.icon}
                </svg>
                <span className="side-label">{n.label}</span>
              </Link>
            </li>
          ))}
        </ul>
      </nav>

      {/* 2. Đem thông tin user và nút logout xuống góc dưới sidebar */}
      <div className="sidebar-footer">
        {client ? (
          <div className="sidebar-user" title={`${client.name} · ${client.role}`}>
            <div className="sidebar-user-avatar" aria-hidden>
              {client.name.charAt(0).toUpperCase()}
            </div>
            {!collapsed && (
              <div className="sidebar-user-details">
                <span className="sidebar-user-name">{client.name}</span>
                <span className="sidebar-user-role">{client.role}</span>
              </div>
            )}
            <button
              type="button"
              className="sidebar-logout-btn"
              onClick={onLogout}
              title="Sign out"
              aria-label="Sign out"
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden
              >
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
            </button>
          </div>
        ) : (
          <div className="sidebar-guest">
            <Link
              to="/"
              className="sidebar-signin-link"
              onClick={onNavigate}
              title={collapsed ? "Staff sign in" : undefined}
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden
              >
                <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" />
                <polyline points="10 17 15 12 10 7" />
                <line x1="15" y1="12" x2="3" y2="12" />
              </svg>
              {!collapsed && <span className="side-label">Staff Sign In</span>}
            </Link>
          </div>
        )}
      </div>
    </aside>
  );
}
