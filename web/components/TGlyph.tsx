// Titan's own mark: a heavy "T" drawn as a shield top. Our glyph, not a carrier logo (D-004).
type Props = { size?: number; className?: string; title?: string; tone?: "accent" | "ink" | "light" };

const FILL = { accent: "var(--accent)", ink: "var(--ink)", light: "#ffffff" } as const;

export function TGlyph({ size = 32, className, title = "Titan", tone = "accent" }: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      role="img"
      aria-label={title}
      className={className}
    >
      <path
        fill={FILL[tone]}
        d="M4 4h24v7h-8.5v13.2c0 1.6-.9 3-2.3 3.7L16 28.6l-1.2-.7c-1.4-.7-2.3-2.1-2.3-3.7V11H4z"
      />
    </svg>
  );
}

export function Wordmark({ size = 28, tone = "accent" }: { size?: number; tone?: Props["tone"] }) {
  return (
    <span className="inline-flex items-center gap-2 font-semibold tracking-tight" style={{ fontSize: size * 0.8 }}>
      <TGlyph size={size} tone={tone} title="" />
      <span>Titan</span>
    </span>
  );
}
