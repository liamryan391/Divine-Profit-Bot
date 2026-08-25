import type { FormEvent } from "react";
import { KeyRound, Landmark, Mail, ShieldCheck, UserRound } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { AuthStatus } from "../types";
import { BrandLockup } from "./brand";
import { Button, Field } from "./ui";

export function AuthGate({
  auth,
  busy,
  onSubmit,
}: {
  auth: AuthStatus;
  busy: string;
  onSubmit: (event: FormEvent<HTMLFormElement>, path: string, success: string) => Promise<void>;
}) {
  return (
    <section className="grid w-[min(980px,100%)] gap-4 lg:grid-cols-[1.03fr_0.97fr]">
      <article className="temple-panel grid gap-6">
        <BrandLockup />
        {auth.setup_required ? (
          <form className="grid gap-3" onSubmit={(event) => void onSubmit(event, "/api/auth/setup", "Owner account created")}>
            <h2 className="text-xl font-black text-temple-gold">Owner Setup</h2>
            <Field label="Username" name="username" autoComplete="username" required />
            <Field label="Display Name" name="display_name" autoComplete="name" placeholder="Creator" />
            <Field label="Recovery Email" name="recovery_email" type="email" autoComplete="email" placeholder="owner@example.com" />
            <Field label="Password" name="password" type="password" autoComplete="new-password" minLength={10} required />
            <Button icon={ShieldCheck} disabled={busy === "/api/auth/setup"} type="submit">
              Create Owner
            </Button>
          </form>
        ) : (
          <form className="grid gap-3" onSubmit={(event) => void onSubmit(event, "/api/auth/login", "Signed in")}>
            <h2 className="text-xl font-black text-temple-gold">Owner Login</h2>
            <Field label="Username" name="username" autoComplete="username" required />
            <Field label="Password" name="password" type="password" autoComplete="current-password" required />
            <Button icon={Landmark} disabled={busy === "/api/auth/login"} type="submit">
              Enter Temple
            </Button>
          </form>
        )}
      </article>
      <RecoveryRunbook setupRequired={auth.setup_required} />
    </section>
  );
}

function RecoveryRunbook({ setupRequired }: { setupRequired: boolean }) {
  return (
    <aside className="temple-panel grid content-start gap-4">
      <div className="section-heading">
        <h2 className="flex items-center gap-2 text-lg font-black">
          <KeyRound aria-hidden="true" className="text-temple-gold" size={20} />
          Recovery Readiness
        </h2>
      </div>
      <RecoveryItem icon={UserRound} label="Forgot Username" command="python -m divine_tool account list" />
      <RecoveryItem icon={KeyRound} label="Forgot Password" command="python -m divine_tool account reset-password <username>" />
      <div className="temple-row grid gap-1 border-l-4 border-l-temple-blue">
        <strong className="flex items-center gap-2">
          <Mail aria-hidden="true" className="text-temple-blue" size={17} />
          Recovery Email
        </strong>
        <span className="text-sm leading-6 text-temple-muted">
          {setupRequired ? "Add it during setup as an owner reference." : "Manage it from Settings after signing in."}
        </span>
      </div>
      <p className="text-sm leading-6 text-temple-muted">
        Passwords are salted hashes and cannot be displayed. Reset creates a new password and signs out existing sessions.
      </p>
    </aside>
  );
}

function RecoveryItem({ icon: Icon, label, command }: { icon: LucideIcon; label: string; command: string }) {
  return (
    <div className="temple-row grid gap-2 border-l-4 border-l-temple-gold">
      <strong className="flex items-center gap-2">
        <Icon aria-hidden="true" className="text-temple-gold" size={17} />
        {label}
      </strong>
      <code className="break-words rounded-md bg-[#091020] px-2.5 py-2 font-mono text-xs leading-5 text-[#d9e5ff]">{command}</code>
    </div>
  );
}
