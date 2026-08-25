import type { FormEvent } from "react";
import { Landmark, ShieldCheck } from "lucide-react";
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
    <section className="temple-panel grid w-[min(520px,100%)] gap-6">
      <BrandLockup />
      {auth.setup_required ? (
        <form className="grid gap-3" onSubmit={(event) => void onSubmit(event, "/api/auth/setup", "Owner account created")}>
          <h2 className="text-xl font-black text-temple-gold">Owner Setup</h2>
          <Field label="Username" name="username" autoComplete="username" required />
          <Field label="Display Name" name="display_name" autoComplete="name" placeholder="Creator" />
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
    </section>
  );
}
