import { TGlyph } from "@/components/TGlyph";

/** Titan Guardian lockup on black: T-Mobile's T is the first letter of "Titan" (T + "itan"). */
export function GuardianMark({ size = 36, product = true }: { size?: number; product?: boolean }) {
  return (
    <span
      role="img"
      aria-label={product ? "Titan Guardian" : "Titan"}
      className="inline-flex flex-none items-end font-extrabold leading-[0.74] tracking-[-0.035em] text-white"
      style={{ fontSize: Math.round(size * 1.39) }}
    >
      <TGlyph size={size} title="" />
      <span aria-hidden style={{ marginLeft: Math.max(1, Math.round(size * 0.03)) }}>
        itan
      </span>
      {product && (
        <span
          aria-hidden
          className="hidden font-semibold tracking-[-0.01em] text-[var(--g-ink-2)] sm:inline"
          style={{ fontSize: "0.5em", marginLeft: "0.45em", lineHeight: 1, paddingBottom: "0.04em" }}
        >
          Guardian
        </span>
      )}
    </span>
  );
}
