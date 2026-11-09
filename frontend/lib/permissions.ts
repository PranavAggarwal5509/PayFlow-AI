/** Permission names mirror backend app.core.security.Permission. */
export const P = {
  INVOICES_VIEW: "invoices:view",
  INVOICES_UPLOAD: "invoices:upload",
  REVIEW_ACT: "review:act",
  REVIEW_HIGH_VALUE: "review:approve_high_value",
  MASTERDATA_VIEW: "masterdata:view",
  MASTERDATA_EDIT: "masterdata:edit",
  SETTINGS_VIEW: "settings:view",
  DEVELOPER_VIEW: "developer:view",
  DEMO_RESET: "demo:reset",
} as const;

export const PERMISSION_LABELS: Record<string, string> = {
  "invoices:view": "View invoices & decisions",
  "invoices:upload": "Upload & reprocess invoices",
  "review:act": "Approve / reject in review queue",
  "review:approve_high_value": "Approve above the authority limit",
  "masterdata:view": "View vendors & purchase orders",
  "masterdata:edit": "Edit vendors, bank details & POs",
  "settings:view": "View controls & business rules",
  "developer:view": "Developer analytics",
  "users:manage": "Manage users & roles",
  "demo:reset": "Reset demo workspace",
};

/** Which permission each route needs (used by the nav and the route guard). */
export const ROUTE_PERMISSIONS: { prefix: string; permission: string }[] = [
  { prefix: "/upload", permission: P.INVOICES_UPLOAD },
  { prefix: "/settings", permission: P.SETTINGS_VIEW },
  { prefix: "/developer", permission: P.DEVELOPER_VIEW },
  { prefix: "/vendors", permission: P.MASTERDATA_VIEW },
  { prefix: "/purchase-orders", permission: P.MASTERDATA_VIEW },
];

export function permissionForPath(pathname: string): string | null {
  return ROUTE_PERMISSIONS.find((r) => pathname === r.prefix || pathname.startsWith(`${r.prefix}/`))?.permission ?? null;
}

export const ROLE_STYLE: Record<string, { gradient: string; ring: string; text: string; soft: string; dot: string }> = {
  ADMIN: { gradient: "from-indigo-500 to-violet-600", ring: "ring-indigo-300", text: "text-indigo-700", soft: "bg-indigo-50", dot: "bg-indigo-500" },
  FINANCE_MANAGER: { gradient: "from-emerald-500 to-teal-600", ring: "ring-emerald-300", text: "text-emerald-700", soft: "bg-emerald-50", dot: "bg-emerald-500" },
  AP_REVIEWER: { gradient: "from-amber-500 to-orange-600", ring: "ring-amber-300", text: "text-amber-800", soft: "bg-amber-50", dot: "bg-amber-500" },
  AP_CLERK: { gradient: "from-sky-500 to-blue-600", ring: "ring-sky-300", text: "text-sky-700", soft: "bg-sky-50", dot: "bg-sky-500" },
  AUDITOR: { gradient: "from-slate-500 to-slate-700", ring: "ring-slate-300", text: "text-slate-700", soft: "bg-slate-100", dot: "bg-slate-500" },
};

export const initialsOf = (name: string): string =>
  name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();
