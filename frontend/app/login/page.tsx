"use client";

import { ArrowRight, Check, Eye, EyeOff, Loader2, Lock, Mail, ShieldCheck, Sparkles, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { toast } from "sonner";

import { useAuth } from "@/components/auth/auth-provider";
import { DecisionPreview } from "@/components/auth/decision-preview";
import { Logo } from "@/components/layout/top-nav";
import { useAsync } from "@/hooks/use-async";
import { ApiError } from "@/lib/api";
import { initialsOf, PERMISSION_LABELS, ROLE_STYLE } from "@/lib/permissions";
import { forgetAccount, getSavedAccounts, type SavedAccount } from "@/lib/session";
import { cn } from "@/lib/utils";
import { authService, type DemoAccount, type RoleInfo } from "@/services";

export default function LoginPage() {
  const router = useRouter();
  const { user, ready, login, logout } = useAuth();
  const catalogue = useAsync(() => authService.roles(), []);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [shake, setShake] = useState(0);
  const [saved, setSaved] = useState<SavedAccount[]>([]);
  const [next, setNext] = useState("/dashboard");
  const [expired, setExpired] = useState(false);

  useEffect(() => {
    setSaved(getSavedAccounts());
    const params = new URLSearchParams(window.location.search);
    const target = params.get("next");
    if (target && target.startsWith("/") && !target.startsWith("/login")) setNext(target);
    setExpired(params.get("expired") === "1");
  }, []);

  const roles = catalogue.data?.roles ?? [];
  const demo = catalogue.data?.demo_accounts ?? [];
  const roleOf = (key: string) => roles.find((r) => r.role === key);

  const signIn = async (address: string, secret: string, key: string) => {
    setBusy(key);
    setError(null);
    try {
      const signedIn = await login(address, secret, remember);
      toast.success(`Welcome, ${signedIn.name.split(" ")[0]}`, { description: `Signed in as ${signedIn.role_label}` });
      router.replace(next);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Sign-in failed. Please try again.");
      setShake((n) => n + 1);
      setBusy(null);
    }
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!email || !password) {
      setError("Enter your work email and password.");
      setShake((n) => n + 1);
      return;
    }
    void signIn(email, password, "form");
  };

  const continueAs = (account: SavedAccount) => {
    const match = demo.find((d) => d.email === account.email);
    if (match) void signIn(match.email, match.password, account.email);
    else {
      setEmail(account.email);
      setPassword("");
      document.getElementById("password")?.focus();
    }
  };

  return (
    <div className="flex min-h-screen bg-white">
      {/* ---------- Brand / live preview panel ---------- */}
      <aside className="relative hidden w-[52%] shrink-0 overflow-hidden lg:sticky lg:top-0 lg:flex lg:h-screen lg:flex-col">
        <div aria-hidden className="hero-band absolute inset-0" />
        <div aria-hidden className="login-orb login-orb-a" />
        <div aria-hidden className="login-orb login-orb-b" />
        <div className="relative flex min-h-0 flex-1 flex-col px-12 py-8 xl:px-16">
          <div className="flex shrink-0 items-center gap-3">
            <Logo className="h-10 w-10 rounded-xl" />
            <span className="text-[18px] font-semibold tracking-tight text-white">
              PayFlow<span className="text-indigo-300"> AI</span>
            </span>
          </div>

          {/* Fixed panel: content is centred in the viewport height and never scrolls. */}
          <div className="flex min-h-0 flex-1 flex-col justify-center gap-8 py-6">
          <div className="max-w-xl reveal">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1 text-[12px] font-medium text-indigo-100 ring-1 ring-inset ring-white/15">
              <Sparkles className="h-3.5 w-3.5" /> Accounts payable, on autopilot
            </span>
            <h1 className="mt-5 text-[40px] font-semibold leading-[1.05] tracking-tight text-white xl:text-[48px] [@media(max-height:760px)]:text-[34px]">
              From invoice PDF
              <br />
              to <span className="bg-gradient-to-r from-indigo-200 via-white to-emerald-200 bg-clip-text text-transparent">explained decision</span>
              <br />
              in seconds.
            </h1>
            <p className="mt-5 max-w-md text-[15.5px] leading-relaxed text-slate-300">
              AI reads the document. Twenty-four deterministic controls decide. Every approval, hold and rejection comes
              with its reasons.
            </p>
          </div>

          <div className="reveal" style={{ ["--d" as string]: "200ms" }}>
            <DecisionPreview />
          </div>
          </div>
        </div>
      </aside>

      {/* ---------- Sign-in panel ---------- */}
      <main className="relative flex flex-1 items-center justify-center px-5 py-10 sm:px-10">
        <div aria-hidden className="pointer-events-none absolute inset-0 bg-[radial-gradient(600px_300px_at_80%_0%,rgba(99,102,241,0.08),transparent)]" />
        <div className="relative w-full max-w-[460px]">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <Logo className="h-10 w-10 rounded-xl" />
            <span className="text-[18px] font-semibold tracking-tight text-slate-900">PayFlow AI</span>
          </div>

          {ready && user ? (
            <SignedInCard name={user.name} roleLabel={user.role_label} roleKey={user.role} onContinue={() => router.replace(next)} onSwitch={logout} />
          ) : (
            <>
              <div className="reveal">
                <h2 className="text-[28px] font-semibold tracking-tight text-slate-900">Welcome back</h2>
                <p className="mt-1.5 text-[14.5px] text-slate-500">Sign in to your accounts-payable workspace.</p>
              </div>

              {expired && (
                <p className="mt-4 rounded-lg bg-amber-50 px-3 py-2 text-[13px] text-amber-800 ring-1 ring-inset ring-amber-200">
                  Your session ended. Please sign in again.
                </p>
              )}

              {saved.length > 0 && (
                <section className="mt-6 reveal" style={{ ["--d" as string]: "80ms" }} aria-label="Saved accounts">
                  <p className="text-[12px] font-semibold uppercase tracking-[0.1em] text-slate-400">Continue as</p>
                  <ul className="mt-2 space-y-2">
                    {saved.slice(0, 3).map((account) => {
                      const style = ROLE_STYLE[account.role] ?? ROLE_STYLE.AUDITOR;
                      return (
                        <li key={account.email} className="group relative">
                          <button
                            type="button"
                            disabled={!!busy}
                            onClick={() => continueAs(account)}
                            className="flex w-full items-center gap-3 rounded-xl border border-slate-200 bg-white p-3 pr-10 text-left transition-all duration-200 hover:-translate-y-0.5 hover:border-indigo-300 hover:shadow-lift disabled:opacity-60"
                          >
                            <span className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br text-[13px] font-semibold text-white", style.gradient)}>
                              {initialsOf(account.name)}
                            </span>
                            <span className="min-w-0 flex-1">
                              <span className="block truncate text-[14px] font-semibold text-slate-900">{account.name}</span>
                              <span className="block truncate text-[12px] text-slate-500">
                                {account.role_label} · {account.email}
                              </span>
                            </span>
                            {busy === account.email ? (
                              <Loader2 className="h-4 w-4 animate-spin text-indigo-500" />
                            ) : (
                              <ArrowRight className="h-4 w-4 text-slate-300 transition-transform group-hover:translate-x-0.5 group-hover:text-indigo-500" />
                            )}
                          </button>
                          <button
                            type="button"
                            aria-label={`Forget ${account.email}`}
                            onClick={() => {
                              forgetAccount(account.email);
                              setSaved(getSavedAccounts());
                            }}
                            className="absolute right-2 top-2 rounded-md p-1 text-slate-300 opacity-0 transition-opacity hover:bg-slate-100 hover:text-slate-600 group-hover:opacity-100"
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </section>
              )}

              <form
                key={shake}
                onSubmit={submit}
                noValidate
                className={cn("mt-6 space-y-4 reveal", shake > 0 && "animate-shake")}
                style={{ ["--d" as string]: "120ms" }}
              >
                <Field id="email" label="Work email" icon={Mail}>
                  <input
                    id="email"
                    type="email"
                    autoComplete="username"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@company.com"
                    className="h-11 w-full rounded-lg border border-slate-200 bg-white pl-10 pr-3 text-[14px] outline-none transition-shadow placeholder:text-slate-400 focus:border-indigo-400 focus:shadow-glow"
                  />
                </Field>
                <Field id="password" label="Password" icon={Lock}>
                  <input
                    id="password"
                    type={show ? "text" : "password"}
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="h-11 w-full rounded-lg border border-slate-200 bg-white pl-10 pr-10 text-[14px] outline-none transition-shadow placeholder:text-slate-400 focus:border-indigo-400 focus:shadow-glow"
                  />
                  <button
                    type="button"
                    onClick={() => setShow((v) => !v)}
                    aria-label={show ? "Hide password" : "Show password"}
                    className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                  >
                    {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </Field>

                <label className="flex cursor-pointer select-none items-center gap-2.5 text-[13px] text-slate-600">
                  <span className="relative flex h-[18px] w-[18px] items-center justify-center">
                    <input
                      type="checkbox"
                      checked={remember}
                      onChange={(e) => setRemember(e.target.checked)}
                      className="peer h-[18px] w-[18px] cursor-pointer appearance-none rounded-[5px] border border-slate-300 bg-white transition-colors checked:border-indigo-600 checked:bg-indigo-600"
                    />
                    <Check className="pointer-events-none absolute h-3 w-3 text-white opacity-0 peer-checked:opacity-100" strokeWidth={3} />
                  </span>
                  Keep me signed in on this device
                </label>

                {error && (
                  <p role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-[13px] text-rose-700 ring-1 ring-inset ring-rose-200">
                    {error}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={!!busy}
                  className="group relative flex h-11 w-full items-center justify-center gap-2 overflow-hidden rounded-lg bg-navy-900 text-[14px] font-semibold text-white shadow-lift transition-all hover:bg-navy-800 active:scale-[0.99] disabled:opacity-70"
                >
                  <span className="btn-sheen" aria-hidden />
                  {busy === "form" ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
                  Sign in securely
                </button>
              </form>

              {demo.length > 0 && (
                <section className="mt-9 reveal" style={{ ["--d" as string]: "200ms" }} aria-label="Demo accounts">
                  <div className="flex items-center gap-3">
                    <span className="h-px flex-1 bg-slate-200" />
                    <span className="text-[12px] font-semibold uppercase tracking-[0.1em] text-slate-400">or try a role</span>
                    <span className="h-px flex-1 bg-slate-200" />
                  </div>
                  <ul className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
                    {demo.map((account, i) => (
                      <RoleCard
                        key={account.email}
                        account={account}
                        info={roleOf(account.role)}
                        busy={busy === account.email}
                        disabled={!!busy}
                        delay={260 + i * 60}
                        wide={i === 0}
                        onPick={() => void signIn(account.email, account.password, account.email)}
                      />
                    ))}
                  </ul>
                  <p className="mt-3 text-center text-[11.5px] text-slate-400">
                    Demo workspace with synthetic data. Each role sees only what it is allowed to.
                  </p>
                </section>
              )}
            </>
          )}
        </div>
      </main>
    </div>
  );
}

function Field({ id, label, icon: Icon, children }: { id: string; label: string; icon: typeof Mail; children: React.ReactNode }) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-[13px] font-medium text-slate-700">
        {label}
      </label>
      <div className="relative">
        <Icon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        {children}
      </div>
    </div>
  );
}

function RoleCard({
  account,
  info,
  busy,
  disabled,
  delay,
  wide,
  onPick,
}: {
  account: DemoAccount;
  info: RoleInfo | undefined;
  busy: boolean;
  disabled: boolean;
  delay: number;
  wide: boolean;
  onPick: () => void;
}) {
  const style = ROLE_STYLE[account.role] ?? ROLE_STYLE.AUDITOR;
  return (
    <li className={cn("reveal", wide && "sm:col-span-2")} style={{ ["--d" as string]: `${delay}ms` }}>
      <button
        type="button"
        disabled={disabled}
        onClick={onPick}
        aria-label={`Sign in as ${info?.label ?? account.role} (${account.name})`}
        title={`Can: ${info?.permissions.map((p) => PERMISSION_LABELS[p] ?? p).join(", ") ?? ""}`}
        className="group relative flex h-full w-full items-start gap-3 overflow-hidden rounded-xl border border-slate-200 bg-white p-3 text-left transition-all duration-200 hover:-translate-y-0.5 hover:border-transparent hover:shadow-lift disabled:opacity-60"
      >
        <span className={cn("pointer-events-none absolute inset-0 bg-gradient-to-br opacity-0 transition-opacity duration-300 group-hover:opacity-[0.07]", style.gradient)} />
        <span className={cn("relative flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br text-[12px] font-semibold text-white shadow-sm", style.gradient)}>
          {initialsOf(account.name)}
        </span>
        <span className="relative min-w-0 flex-1">
          <span className="flex items-center gap-2">
            <span className="truncate text-[13.5px] font-semibold text-slate-900">{info?.label ?? account.role}</span>
            {busy && <Loader2 className="h-3.5 w-3.5 animate-spin text-indigo-500" />}
          </span>
          <span className="block truncate text-[12px] text-slate-500">{account.name}</span>
          {wide && info && <span className="mt-1 block text-[12px] leading-snug text-slate-500">{info.summary}</span>}
          {info && (
            <span className="mt-1.5 inline-flex items-center gap-1 text-[11px] font-medium text-slate-400">
              <ShieldCheck className="h-3 w-3" /> {info.permissions.length} permissions
            </span>
          )}
        </span>
      </button>
    </li>
  );
}

function SignedInCard({
  name,
  roleLabel,
  roleKey,
  onContinue,
  onSwitch,
}: {
  name: string;
  roleLabel: string;
  roleKey: string;
  onContinue: () => void;
  onSwitch: () => Promise<void>;
}) {
  const style = ROLE_STYLE[roleKey] ?? ROLE_STYLE.AUDITOR;
  return (
    <div className="reveal rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-lift">
      <span className={cn("mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br text-[16px] font-semibold text-white", style.gradient)}>
        {initialsOf(name)}
      </span>
      <h2 className="mt-4 text-[20px] font-semibold text-slate-900">You are signed in</h2>
      <p className="mt-1 text-[14px] text-slate-500">
        {name} · {roleLabel}
      </p>
      <div className="mt-6 grid gap-2">
        <button type="button" onClick={onContinue} className="h-11 rounded-lg bg-navy-900 text-[14px] font-semibold text-white hover:bg-navy-800">
          Continue to workspace
        </button>
        <button type="button" onClick={() => void onSwitch()} className="h-11 rounded-lg border border-slate-200 text-[14px] font-semibold text-slate-700 hover:bg-slate-50">
          Sign out and switch account
        </button>
      </div>
    </div>
  );
}
