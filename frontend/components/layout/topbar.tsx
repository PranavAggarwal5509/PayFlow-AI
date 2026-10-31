"use client";

import { Bell, ChevronRight, LogOut, Search, Settings as SettingsIcon, User } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { NAV_ITEMS } from "@/components/layout/sidebar";
import { DropdownContent, DropdownItem, DropdownMenu, DropdownTrigger } from "@/components/ui/dropdown";
import { Input } from "@/components/ui/input";
import { dashboardService, settingsService } from "@/services";
import { useAsync } from "@/hooks/use-async";

function titleFor(pathname: string): { title: string; crumbs: { label: string; href: string }[] } {
  const segments = pathname.split("/").filter(Boolean);
  const root = NAV_ITEMS.find((item) => item.href === `/${segments[0]}`);
  const crumbs: { label: string; href: string }[] = [];
  if (root) crumbs.push({ label: root.label, href: root.href });
  if (segments[0] === "processing") crumbs.push({ label: "Live Processing", href: pathname });
  else if (segments.length > 1) crumbs.push({ label: "Details", href: pathname });
  return { title: crumbs[crumbs.length - 1]?.label ?? "PayFlow AI", crumbs };
}

export function Topbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { title, crumbs } = titleFor(pathname);
  const [query, setQuery] = useState("");
  const stats = useAsync(() => dashboardService.stats(), [pathname]);
  const settings = useAsync(() => settingsService.get(), []);
  const pending = stats.data?.pending_reviews ?? 0;

  useEffect(() => setQuery(""), [pathname]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const text = query.trim();
    router.push(text ? `/invoices?q=${encodeURIComponent(text)}` : "/invoices");
  };

  const user = settings.data?.user;
  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-4 border-b bg-white/90 px-6 backdrop-blur">
      <div className="min-w-0">
        <nav aria-label="Breadcrumb" className="flex items-center gap-1 text-xs text-muted-foreground">
          <Link href="/dashboard" className="hover:text-foreground">
            PayFlow
          </Link>
          {crumbs.map((crumb, index) => (
            <span key={crumb.href} className="flex items-center gap-1">
              <ChevronRight className="h-3 w-3" />
              {index < crumbs.length - 1 ? (
                <Link href={crumb.href} className="hover:text-foreground">
                  {crumb.label}
                </Link>
              ) : (
                <span className="text-foreground">{crumb.label}</span>
              )}
            </span>
          ))}
        </nav>
        <h1 className="truncate text-[15px] font-semibold leading-tight">{title}</h1>
      </div>

      <form onSubmit={submit} className="ml-auto hidden w-72 lg:block" role="search">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search invoices, vendors, PO…"
            aria-label="Search invoices"
            className="pl-9"
          />
        </div>
      </form>

      <Link
        href="/review"
        className="relative rounded-md p-2 text-slate-500 hover:bg-slate-100 lg:ml-0"
        aria-label={`${pending} invoices awaiting review`}
      >
        <Bell className="h-[18px] w-[18px]" />
        {pending > 0 && (
          <span className="absolute right-0.5 top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-danger px-1 text-[10px] font-semibold text-white">
            {pending}
          </span>
        )}
      </Link>

      <DropdownMenu>
        <DropdownTrigger
          className="flex items-center gap-2 rounded-full border bg-white py-1 pl-1 pr-3 text-sm hover:bg-slate-50"
          aria-label="User menu"
        >
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-primary">
            <User className="h-4 w-4" />
          </span>
          <span className="hidden text-[13px] font-medium sm:inline">{user?.name ?? "Demo user"}</span>
        </DropdownTrigger>
        <DropdownContent>
          <div className="px-2.5 pb-2 pt-1.5">
            <p className="text-sm font-medium">{user?.name ?? "Demo user"}</p>
            <p className="text-xs text-muted-foreground">{user?.id}</p>
            <p className="mt-1 text-[11px] uppercase tracking-wide text-slate-400">{user?.role}</p>
          </div>
          <DropdownItem onSelect={() => router.push("/settings")}>
            <SettingsIcon className="h-4 w-4" /> Settings
          </DropdownItem>
          <DropdownItem disabled>
            <LogOut className="h-4 w-4" /> Sign out (demo mode)
          </DropdownItem>
        </DropdownContent>
      </DropdownMenu>
    </header>
  );
}

