// Shared class strings for the portal, case and console screens (T-Mobile account UI: flat, small radii,
// one filled primary per screen). Constants only, so screens keep their own markup and data flow.
export const BTN =
  "inline-flex h-12 min-w-[44px] items-center justify-center rounded-control px-6 text-center text-body font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-60";
/** The one magenta action on a screen. Pill is T-Mobile's CTA shape. */
export const BTN_PRIMARY = `${BTN} !rounded-full bg-accent text-accent-ink hover:bg-accent-hover`;
export const BTN_DARK = `${BTN} bg-ink text-surface hover:bg-[#2b2b2b]`;
export const BTN_SECONDARY = `${BTN} border border-line-strong bg-surface text-ink hover:bg-surface-2`;
export const BTN_DANGER = `${BTN} border border-negative bg-surface text-negative hover:bg-negative-soft`;
/** A resting panel: 1px border, no shadow. */
export const PANEL = "rounded-panel border border-line bg-surface";
/** Sentence-case grey label above a value or list. */
export const LABEL = "text-[14px] font-medium leading-5 text-ink-3";
/** A left-ruled notice line in place of a tinted card-in-card. */
export const NOTE = "border-l-4 bg-surface py-3 pl-4 pr-3 text-body";
