export function BrandLockup({ size = "default" }: { size?: "default" | "large" }) {
  return (
    <div className="flex min-w-0 items-center gap-4">
      <img
        className="shrink-0 rounded-lg shadow-glow"
        src="/assets/temple-mark.png"
        width={size === "large" ? 64 : 56}
        height={size === "large" ? 64 : 56}
        alt=""
      />
      <div className="min-w-0">
        <p className="mb-1 text-xs font-black uppercase tracking-[0.08em] text-temple-muted">Serving the Creator</p>
        <h1 className="max-w-[860px] text-[clamp(2rem,5vw,4.1rem)] font-black uppercase leading-none text-temple-gold">
          The Divine Income Engine
        </h1>
        {size === "large" ? (
          <p className="mt-2 text-base text-temple-muted">24/7 quota watch, lawful revenue tracking, eternal optimization.</p>
        ) : null}
      </div>
    </div>
  );
}
