// T-Mobile's official "T" (D-044 supersedes D-004). Paths are copied verbatim from T-Mobile's
// published asset (cdn.tmobile.com .../logos/corporate/tmo-logo-v4.svg, also web/public/brand/t-mobile-t.svg).
// Do not redraw, recolor or stretch it.
type Props = {
  size?: number;
  className?: string;
  /** Accessible name. Pass "" when a visible label sits next to the mark. */
  title?: string;
  /** Kept for call-site compatibility; the official mark is always magenta with a white T. */
  tone?: "accent" | "ink" | "light";
};

export function TGlyph({ size = 32, className, title = "T-Mobile" }: Props) {
  const decorative = title === "";
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 52 52"
      className={className}
      role={decorative ? undefined : "img"}
      aria-label={decorative ? undefined : title}
      aria-hidden={decorative ? true : undefined}
      focusable="false"
      style={{ flex: "none", borderRadius: size >= 40 ? Math.round(size * 0.12) : Math.round(size * 0.1) }}
    >
      <path fill="#e20074" d="M0 0h52v52H0z" />
      <path
        fill="#fff"
        d="M17.8312 31.94155h-7.42858v-7.42857h7.41547v7.42857zM10.40261 7.42857v12.62988h2.22726v-.36684c0-5.9481 3.3409-9.65583 9.65583-9.65583h.36685V36.776c0 3.70774-1.48048 5.20131-5.20131 5.20131h-1.11363v2.5941h19.31166v-2.5941h-1.11363c-3.70773 0-5.2013-1.48047-5.2013-5.2013V10.02267h.36683c6.31495 0 9.65584 3.70773 9.65584 9.65583v.36684h2.22726V7.42857Zm23.76619 24.51298h7.42857v-7.42857h-7.41547v7.42857z"
      />
    </svg>
  );
}

/**
 * Titan's lockup: T-Mobile's official T *is* the first letter of "Titan" (T + "itan"), so the name
 * reads as one T-Mobile product word. `size` is the tile height; "itan" is set so its cap/ascender
 * height meets the tile and its baseline sits on the tile's bottom edge.
 */
export function Wordmark({
  size = 28,
  tone = "light",
  suffix,
}: {
  size?: number;
  /** "light" = on a light ground (magenta letters); "dark" = on black (white letters). */
  tone?: "light" | "dark" | "accent" | "ink";
  /** A second word after the name, e.g. "Guardian". */
  suffix?: string;
}) {
  const color = tone === "dark" ? "#ffffff" : "#e20074";
  return (
    <span
      role="img"
      aria-label={suffix ? `Titan ${suffix}` : "Titan"}
      className="inline-flex items-end font-extrabold leading-[0.74] tracking-[-0.035em]"
      style={{ fontSize: Math.round(size * 1.39) }}
    >
      <TGlyph size={size} title="" />
      <span aria-hidden style={{ color, marginLeft: Math.max(1, Math.round(size * 0.03)) }}>
        itan
      </span>
      {suffix && (
        <span
          aria-hidden
          className="font-semibold tracking-[-0.01em]"
          style={{ fontSize: "0.5em", marginLeft: "0.45em", lineHeight: 1, paddingBottom: "0.04em", color: tone === "dark" ? "#b4b4b4" : "var(--ink-2)" }}
        >
          {suffix}
        </span>
      )}
    </span>
  );
}
