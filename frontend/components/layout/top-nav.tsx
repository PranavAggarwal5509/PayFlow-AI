"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import {
  Bell,
  Building2,
  ChevronDown,
  ClipboardCheck,
  CornerDownLeft,
  FileText,
  LayoutGrid,
  LogOut,
  Menu,
  Search,
  ShieldCheck,
  ShoppingCart,
  SlidersHorizontal,
  Terminal,
  Upload,
  Users,
  X,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { DropdownContent, DropdownItem, DropdownMenu, DropdownTrigger } from "@/components/ui/dropdown";
import { useAsync } from "@/hooks/use-async";
import { initialsOf, permissionForPath, ROLE_STYLE } from "@/lib/permissions";
import { SAMPLE_INVOICES } from "@/lib/samples";
import { cn } from "@/lib/utils";
import { dashboardService } from "@/services";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

const PRIMARY: NavItem[] = [
  { href: "/dashboard", label: "Overview", icon: LayoutGrid },
  { href: "/upload", label: "Process", icon: Upload },
  { href: "/invoices", label: "Invoices", icon: FileText },
  { href: "/review", label: "Review", icon: ClipboardCheck },
];

const MASTER: NavItem[] = [
  { href: "/vendors", label: "Vendors", icon: Building2 },
  { href: "/purchase-orders", label: "Purchase orders", icon: ShoppingCart },
];

const SYSTEM: NavItem[] = [
  { href: "/settings", label: "Controls & rules", icon: SlidersHorizontal },
  { href: "/developer", label: "Developer", icon: Terminal },
];

export const NAV_ITEMS = [...PRIMARY, ...MASTER, ...SYSTEM];

const isActive = (pathname: string, href: string) => pathname === href || pathname.startsWith(`${href}/`);

export function TopNav() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, can, logout } = useAuth();
  const stats = useAsync(() => dashboardService.stats(), [pathname]);
  // Other components announce data changes (e.g. a demo reset) so the badges refresh immediately.
  useEffect(() => {
    const reload = () => stats.reload();
    window.addEventListener("payflow:data-changed", reload);
    return () => window.removeEventListener("payflow:data-changed", reload);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const pending = stats.data?.pending_reviews ?? 0;
  const allowed = (item: NavItem) => {
    const needed = permissionForPath(item.href);
    return !needed || can(needed);
  };
  const primary = PRIMARY.filter(allowed);
  const master = MASTER.filter(allowed);
  const system = SYSTEM.filter(allowed);
  const roleStyle = ROLE_STYLE[user?.role ?? ""] ?? ROLE_STYLE.ADMIN;
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const masterActive = master.some((m) => isActive(pathname, m.href));

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => setMobileOpen(false), [pathname]);

  const initials = initialsOf(user?.name ?? "PayFlow User");

  return (
    <header className="sticky top-0 z-40 border-b border-white/[0.06] bg-navy-950/95 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-[1480px] items-center gap-3 px-4 sm:px-6 lg:px-8">
        <Link href="/dashboard" className="mr-2 flex shrink-0 items-center gap-2.5" aria-label="PayFlow AI home">
          <Logo />
          <span className="hidden text-[15px] font-semibold tracking-tight text-white sm:inline">
            PayFlow<span className="text-indigo-300"> AI</span>
          </span>
        </Link>

        <nav className="hidden items-center gap-0.5 lg:flex" aria-label="Main">
          {primary.map((item) => (
            <NavLink key={item.href} item={item} active={isActive(pathname, item.href)} count={item.href === "/review" ? pending : 0} />
          ))}
          {master.length > 0 && (
          <DropdownMenu>
            <DropdownTrigger
              className={cn(
                "flex items-center gap-1.5 whitespace-nowrap rounded-lg px-3 py-2 text-[13.5px] font-medium transition-colors",
                masterActive ? "bg-white/10 text-white" : "text-slate-400 hover:bg-white/[0.06] hover:text-white",
              )}
            >
              Master data <ChevronDown className="h-3.5 w-3.5 opacity-70" />
            </DropdownTrigger>
            <DropdownContent>
              {master.map((item) => (
                <DropdownItem key={item.href} onSelect={() => router.push(item.href)}>
                  <item.icon className="h-4 w-4" /> {item.label}
                </DropdownItem>
              ))}
            </DropdownContent>
          </DropdownMenu>
          )}
          {system.slice(0, 1).map((item) => (
            <NavLink key={item.href} item={item} active={isActive(pathname, item.href)} />
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <button
            type="button"
            onClick={() => setPaletteOpen(true)}
            className="group hidden h-9 w-64 items-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] px-3 text-left text-[13px] text-slate-400 transition-colors hover:border-white/20 hover:bg-white/[0.07] xl:flex"
          >
            <Search className="h-4 w-4" />
            <span className="flex-1">Search or jump to…</span>
            <kbd className="rounded border border-white/10 bg-white/5 px-1.5 py-px font-sans text-[10.5px] text-slate-400">Ctrl K</kbd>
          </button>
          <button
            type="button"
            onClick={() => setPaletteOpen(true)}
            className="rounded-lg p-2 text-slate-400 hover:bg-white/10 hover:text-white xl:hidden"
            aria-label="Search"
          >
            <Search className="h-[18px] w-[18px]" />
          </button>
          <Link
            href="/review"
            className="relative rounded-lg p-2 text-slate-400 transition-colors hover:bg-white/10 hover:text-white"
            aria-label={`${pending} invoices awaiting review`}
          >
            <Bell className="h-[18px] w-[18px]" />
            {pending > 0 && (
              <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-amber-400 px-1 text-[10px] font-bold text-navy-950">
                {pending}
              </span>
            )}
          </Link>
          <DropdownMenu>
            <DropdownTrigger
              className="flex items-center gap-2 rounded-full p-0.5 pr-0.5 transition-colors hover:bg-white/10 xl:pr-3"
              aria-label="User menu"
            >
              <span className={cn("flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br text-[12px] font-semibold text-white ring-2 ring-white/10", roleStyle.gradient)}>
                {initials}
              </span>
              <span className="hidden whitespace-nowrap text-left leading-tight xl:block">
                <span className="block text-[12.5px] font-medium text-white">{user?.name}</span>
                <span className="block text-[10.5px] uppercase tracking-wider text-slate-400">{user?.role_label}</span>
              </span>
            </DropdownTrigger>
            <DropdownContent>
              <div className="min-w-[220px] px-2.5 pb-2.5 pt-1.5">
                <p className="text-sm font-semibold">{user?.name}</p>
                <p className="text-xs text-muted-foreground">{user?.email}</p>
                <span className={cn("mt-2 inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-semibold", roleStyle.soft, roleStyle.text)}>
                  <span className={cn("h-1.5 w-1.5 rounded-full", roleStyle.dot)} /> {user?.role_label}
                </span>
              </div>
              {system.map((item) => (
                <DropdownItem key={item.href} onSelect={() => router.push(item.href)}>
                  <item.icon className="h-4 w-4" /> {item.label}
                </DropdownItem>
              ))}
              <DropdownItem onSelect={() => void logout()}>
                <Users className="h-4 w-4" /> Switch account
              </DropdownItem>
              <DropdownItem onSelect={() => void logout()}>
                <LogOut className="h-4 w-4" /> Sign out
              </DropdownItem>
            </DropdownContent>
          </DropdownMenu>
          <button
            type="button"
            className="rounded-lg p-2 text-slate-300 hover:bg-white/10 lg:hidden"
            aria-label="Open navigation"
            aria-expanded={mobileOpen}
            onClick={() => setMobileOpen((open) => !open)}
          >
            {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {mobileOpen && (
        <nav className="border-t border-white/[0.06] px-4 pb-4 pt-2 lg:hidden" aria-label="Mobile">
          {[...primary, ...master, ...system].map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-[14px] font-medium",
                isActive(pathname, item.href) ? "bg-white/10 text-white" : "text-slate-300",
              )}
            >
              <item.icon className="h-4 w-4" /> {item.label}
              {item.href === "/review" && pending > 0 && (
                <span className="ml-auto rounded-full bg-amber-400 px-2 text-[11px] font-bold text-navy-950">{pending}</span>
              )}
            </Link>
          ))}
        </nav>
      )}

      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
    </header>
  );
}

function NavLink({ item, active, count = 0 }: { item: NavItem; active: boolean; count?: number }) {
  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "relative flex items-center gap-2 whitespace-nowrap rounded-lg px-3 py-2 text-[13.5px] font-medium transition-colors duration-150",
        active ? "bg-white/10 text-white" : "text-slate-400 hover:bg-white/[0.06] hover:text-white",
      )}
    >
      {item.label}
      {count > 0 && (
        <span className="rounded-full bg-amber-400/15 px-1.5 text-[11px] font-semibold tabular text-amber-300 ring-1 ring-inset ring-amber-400/30">
          {count}
        </span>
      )}
      {active && <span className="absolute inset-x-3 -bottom-[13px] h-0.5 rounded-full bg-indigo-400" />}
    </Link>
  );
}

export function Logo({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "flex h-8 w-8 items-center justify-center rounded-[10px] bg-gradient-to-br from-indigo-400 via-indigo-500 to-violet-600 shadow-[0_6px_20px_-6px_rgba(129,140,248,0.8)]",
        className,
      )}
    >
      <svg viewBox="0 0 24 24" className="h-4 w-4 text-white" fill="none" stroke="currentColor" strokeWidth={2.4}>
        <path d="M5 12h9M10 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M19 5v14" strokeLinecap="round" />
      </svg>
    </span>
  );
}

interface Command {
  id: string;
  label: string;
  hint: string;
  icon: LucideIcon;
  run: () => void;
}

function CommandPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const router = useRouter();
  const { can } = useAuth();
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState(0);
  const listRef = useRef<HTMLUListElement>(null);

  const commands = useMemo<Command[]>(() => {
    const go = (href: string) => () => router.push(href);
    return [
      ...NAV_ITEMS.filter((item) => {
        const needed = permissionForPath(item.href);
        return !needed || can(needed);
      }).map((item) => ({ id: item.href, label: item.label, hint: "Go to page", icon: item.icon, run: go(item.href) })),
      ...(can("invoices:upload") ? SAMPLE_INVOICES : []).map((s) => ({
        id: s.file,
        label: s.scenario,
        hint: `Scenario · ${s.edge_case_category}`,
        icon: ShieldCheck,
        run: go(`/upload?scenario=${encodeURIComponent(s.file)}`),
      })),
    ];
  }, [router, can]);

  const text = query.trim().toLowerCase();
  const results = text ? commands.filter((c) => `${c.label} ${c.hint}`.toLowerCase().includes(text)) : commands.slice(0, 9);
  const searchEntry: Command | null = text
    ? {
        id: "search",
        label: `Search invoices for “${query.trim()}”`,
        hint: "Invoice number, vendor, PO or file",
        icon: Search,
        run: () => router.push(`/invoices?q=${encodeURIComponent(query.trim())}`),
      }
    : null;
  const items = searchEntry ? [searchEntry, ...results] : results;

  useEffect(() => {
    setIndex(0);
  }, [query]);
  useEffect(() => {
    if (!open) setQuery("");
  }, [open]);

  const choose = (command: Command | undefined) => {
    if (!command) return;
    onOpenChange(false);
    command.run();
  };

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-navy-950/60 backdrop-blur-sm data-[state=open]:animate-in data-[state=open]:fade-in-0" />
        <DialogPrimitive.Content className="fixed left-1/2 top-[14vh] z-50 w-[calc(100%-2rem)] max-w-xl -translate-x-1/2 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-pop focus:outline-none data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95">
          <DialogPrimitive.Title className="sr-only">Command palette</DialogPrimitive.Title>
          <DialogPrimitive.Description className="sr-only">Search invoices, jump to pages or run a scenario.</DialogPrimitive.Description>
          <div className="flex items-center gap-3 border-b border-slate-100 px-4">
            <Search className="h-4 w-4 text-slate-400" />
            <input
              autoFocus
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "ArrowDown") {
                  event.preventDefault();
                  setIndex((i) => Math.min(i + 1, items.length - 1));
                } else if (event.key === "ArrowUp") {
                  event.preventDefault();
                  setIndex((i) => Math.max(i - 1, 0));
                } else if (event.key === "Enter") {
                  event.preventDefault();
                  choose(items[index]);
                }
              }}
              placeholder="Search invoices, jump to a page, run a scenario…"
              className="h-14 flex-1 bg-transparent text-[15px] text-slate-900 outline-none placeholder:text-slate-400"
              aria-label="Command"
            />
            <kbd className="rounded border border-slate-200 px-1.5 py-px text-[10.5px] text-slate-400">Esc</kbd>
          </div>
          <ul ref={listRef} className="max-h-[360px] overflow-y-auto p-2" role="listbox">
            {items.length === 0 && <li className="px-3 py-6 text-center text-sm text-slate-500">No matches.</li>}
            {items.map((command, i) => (
              <li key={command.id} role="option" aria-selected={i === index}>
                <button
                  type="button"
                  onMouseEnter={() => setIndex(i)}
                  onClick={() => choose(command)}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left",
                    i === index ? "bg-indigo-50" : "hover:bg-slate-50",
                  )}
                >
                  <span
                    className={cn(
                      "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
                      i === index ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-500",
                    )}
                  >
                    <command.icon className="h-4 w-4" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[13.5px] font-medium text-slate-900">{command.label}</span>
                    <span className="block truncate text-[12px] text-slate-500">{command.hint}</span>
                  </span>
                  {i === index && <CornerDownLeft className="h-4 w-4 text-indigo-500" />}
                </button>
              </li>
            ))}
          </ul>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
