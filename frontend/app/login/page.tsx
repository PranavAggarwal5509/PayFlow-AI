"use client";

import { Check, ChevronDown, Eye, EyeOff, Loader2, Lock, Mail, ShieldCheck, Sparkles, UserCog } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { toast } from "sonner";

import { useAuth } from "@/components/auth/auth-provider";
import { DecisionPreview } from "@/components/auth/decision-preview";
import { Logo } from "@/components/layout/top-nav";
import { useAsync } from "@/hooks/use-async";
import { ApiError } from "@/lib/api";
import { initialsOf, ROLE_STYLE } from "@/lib/permissions";
import { cn } from "@/lib/utils";
import { authService } from "@/services";

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
  const [next, setNext] = useState("/dashboard");
  const [expired, setExpired] = useState(false);
  // Fields stay read-only until the user focuses them, so the browser's saved-password manager
  // cannot silently pre-fill an unrelated login when the page loads.
  const [armed, setArmed] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const target = params.get("next");
    if (target && target.startsWith("/") && !target.startsWith("/login")) setNext(target);
    setExpired(params.get("expired") === "1");
  }, []);

  const roles = catalogue.data?.roles ?? [];
  const demo = catalogue.data?.demo_accounts ?? [];
  const roleOf = (key: string) => roles.find((r) => r.role === key);
  // The dropdown reflects the fields: editing the email or password by hand clears the selection.
  const selectedDemo = demo.find((d) => d.email === email && d.password === password)?.email ?? "";

  const pickDemo = (address: string) => {
    const account = demo.find((d) => d.email === address);
    setError(null);
    if (!account) {
      setEmail("");
      setPassword("");
      return;
    }
    setArmed(true);
    setEmail(account.email);
    setPassword(account.password);
    setShow(true);
  };

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

              <form
                key={shake}
                onSubmit={submit}
                noValidate
                className={cn("mt-6 space-y-4 reveal", shake > 0 && "animate-shake")}
                style={{ ["--d" as string]: "120ms" }}
              >
                {demo.length > 0 && (
                  <div>
                    <Field id="demo-role" label="Demo role" icon={UserCog}>
                      <select
                        id="demo-role"
                        value={selectedDemo}
                        onChange={(e) => pickDemo(e.target.value)}
                        aria-describedby="demo-role-hint"
                        className="h-11 w-full cursor-pointer appearance-none rounded-lg border border-indigo-200 bg-indigo-50/40 pl-10 pr-9 text-[14px] text-slate-900 outline-none transition-shadow focus:border-indigo-400 focus:shadow-glow"
                      >
                        <option value="">Select a role to fill in its login…</option>
                        {demo.map((account) => (
                          <option key={account.email} value={account.email}>
                            {roleOf(account.role)?.label ?? account.role} — {account.name}
                          </option>
                        ))}
                      </select>
                      <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                    </Field>
                    <p id="demo-role-hint" className="mt-1.5 text-[12px] text-slate-500">
                      {selectedDemo
                        ? `Filled ${selectedDemo} / ${password}. Press "Sign in securely".`
                        : "Demo workspace: pick a role and its email and password are filled in for you."}
                    </p>
                  </div>
                )}
                <Field id="email" label="Work email" icon={Mail}>
                  <input
                    id="email"
                    name="payflow-email"
                    type="email"
                    autoComplete="off"
                    readOnly={!armed}
                    onFocus={() => setArmed(true)}
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="e.g. finance@payflow.demo"
                    className="h-11 w-full rounded-lg border border-slate-200 bg-white pl-10 pr-3 text-[14px] outline-none transition-shadow placeholder:text-slate-400 focus:border-indigo-400 focus:shadow-glow"
                  />
                </Field>
                <Field id="password" label="Password" icon={Lock}>
                  <input
                    id="password"
                    name="payflow-password"
                    readOnly={!armed}
                    onFocus={() => setArmed(true)}
                    type={show ? "text" : "password"}
                    autoComplete="new-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your password"
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
