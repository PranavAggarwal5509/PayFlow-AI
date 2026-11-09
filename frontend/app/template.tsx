import type { ReactNode } from "react";

/** Re-mounted on every navigation: gives each page a soft fade-up entrance. */
export default function Template({ children }: { children: ReactNode }) {
  return <div className="page-enter">{children}</div>;
}
