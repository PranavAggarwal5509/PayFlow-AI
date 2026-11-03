"use client";

import {
  Activity,
  Building2,
  ClipboardCheck,
  FileText,
  LayoutDashboard,
  Settings,
  ShoppingCart,
  Terminal,
  Upload,
  Workflow,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/invoices", label: "Invoices", icon: FileText },
  { href: "/upload", label: "Upload Invoice", icon: Upload },
  { href: "/review", label: "Review Queue", icon: ClipboardCheck },
  { href: "/vendors", label: "Vendors", icon: Building2 },
  { href: "/purchase-orders", label: "Purchase Orders", icon: ShoppingCart },
  { href: "/activity", label: "Processing Activity", icon: Activity },
  { href: "/developer", label: "Developer", icon: Terminal },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="sticky top-0 hidden h-screen w-[232px] shrink-0 flex-col border-r bg-white md:flex">
      <div className="flex h-14 items-center gap-2.5 border-b px-5">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-white">
          <Workflow className="h-4 w-4" />
        </div>
        <span className="text-[15px] font-semibold tracking-tight">PayFlow AI</span>
      </div>
      <nav className="flex-1 space-y-0.5 overflow-y-auto p-3" aria-label="Main">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex items-center gap-2.5 rounded-md px-3 py-2 text-[13.5px] font-medium transition-colors",
                active
                  ? "bg-blue-50 text-primary"
                  : "text-slate-600 hover:bg-slate-100 hover:text-foreground",
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t p-4 text-[11px] leading-snug text-muted-foreground">
        Demo environment · synthetic data only
      </div>
    </aside>
  );
}

export const NAV_ITEMS = NAV;

