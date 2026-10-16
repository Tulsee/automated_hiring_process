/**
 * Inline icon set.
 *
 * The stylesheet colours icons with `currentColor` and sizes them inside
 * buttons, so icons are inlined SVG rather than an icon font or <img>: that is
 * what lets `.nav-item--active svg { color: #fff }` work.
 *
 * Icons are decorative by default (`aria-hidden`), because the control around
 * them carries the accessible name. Pass a `title` only when an icon is the
 * sole content of a control and nothing else names it.
 */

export type IconName =
  | "search"
  | "bell"
  | "settings"
  | "help"
  | "menu"
  | "close"
  | "chevron-right"
  | "chevron-down"
  | "chevron-up"
  | "arrow-right"
  | "users"
  | "briefcase"
  | "clipboard"
  | "calendar"
  | "sparkles"
  | "plus"
  | "info"
  | "check"
  | "alert"
  | "upload"
  | "play"
  | "clock"
  | "pin"
  | "trending"
  | "file"
  | "quote"
  | "mic"
  | "external"
  | "sun";

const PATHS: Record<IconName, string> = {
  search: "M11 11 15 15M9.5 6.5a3.5 3.5 0 1 1-7 0 3.5 3.5 0 0 1 7 0Z",
  bell: "M8 2.5a3.5 3.5 0 0 0-3.5 3.5c0 3-1.5 4-1.5 4h10s-1.5-1-1.5-4A3.5 3.5 0 0 0 8 2.5ZM6.5 12.5a1.5 1.5 0 0 0 3 0",
  // A toothed gear. The previous drawing was a circle with eight radiating
  // ticks, which is a sun — indistinguishable from the `sun` icon beside it.
  settings:
    "M8 9.8a1.8 1.8 0 1 0 0-3.6 1.8 1.8 0 0 0 0 3.6ZM6.9 2.2a1.1 1.1 0 0 1 2.2 0l.1.9 1 .4.8-.5a1.1 1.1 0 0 1 1.5 1.5l-.5.8.4 1 .9.1a1.1 1.1 0 0 1 0 2.2l-.9.1-.4 1 .5.8a1.1 1.1 0 0 1-1.5 1.5l-.8-.5-1 .4-.1.9a1.1 1.1 0 0 1-2.2 0l-.1-.9-1-.4-.8.5a1.1 1.1 0 0 1-1.5-1.5l.5-.8-.4-1-.9-.1a1.1 1.1 0 0 1 0-2.2l.9-.1.4-1-.5-.8a1.1 1.1 0 0 1 1.5-1.5l.8.5 1-.4Z",
  help: "M8 14A6 6 0 1 0 8 2a6 6 0 0 0 0 12ZM6.4 6.2A1.7 1.7 0 0 1 9.7 7c0 1.1-1.7 1.3-1.7 2.3M8 11.6h.01",
  menu: "M2.5 4.5h11M2.5 8h11M2.5 11.5h11",
  close: "M4 4l8 8M12 4l-8 8",
  "chevron-right": "M6.5 4l4 4-4 4",
  "chevron-down": "M4 6.5l4 4 4-4",
  "chevron-up": "M12 9.5l-4-4-4 4",
  "arrow-right": "M3 8h10M9.5 4.5 13 8l-3.5 3.5",
  users:
    "M10.5 13.5v-1a2.5 2.5 0 0 0-2.5-2.5H5a2.5 2.5 0 0 0-2.5 2.5v1M6.5 7.5a2 2 0 1 0 0-4 2 2 0 0 0 0 4ZM13.5 13.5v-1a2.5 2.5 0 0 0-1.9-2.4M10 3.6a2 2 0 0 1 0 3.9",
  briefcase:
    "M13 5.5H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1v-6a1 1 0 0 0-1-1ZM6 5.5v-1a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v1M2 8.5h12",
  clipboard:
    "M10 2.5h1a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1h1M6 2.5h4v1.5H6zM6 8.5l1.2 1.2L10 7",
  calendar:
    "M12 3.5H4a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1v-8a1 1 0 0 0-1-1ZM5.5 2v2.5M10.5 2v2.5M3 6.8h10",
  sparkles:
    "M8 2.5l1.1 2.9L12 6.5 9.1 7.6 8 10.5 6.9 7.6 4 6.5l2.9-1.1ZM12.5 10.5l.5 1.3 1.3.5-1.3.5-.5 1.3-.5-1.3-1.3-.5 1.3-.5Z",
  plus: "M8 3.5v9M3.5 8h9",
  info: "M8 14A6 6 0 1 0 8 2a6 6 0 0 0 0 12ZM8 7.3v4M8 5.2h.01",
  check: "M3.5 8.5 6.3 11.3 12.5 5",
  alert: "M8 2.8 1.8 13.2h12.4L8 2.8ZM8 6.5v3M8 11.3h.01",
  upload: "M8 11V3M5 6l3-3 3 3M3 11.5v1a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1v-1",
  play: "M5.5 3.5l7 4.5-7 4.5v-9Z",
  clock: "M8 14A6 6 0 1 0 8 2a6 6 0 0 0 0 12ZM8 5v3.2l2.2 1.3",
  pin: "M8 14s4.2-4 4.2-7A4.2 4.2 0 0 0 3.8 7c0 3 4.2 7 4.2 7ZM8 8.3a1.4 1.4 0 1 0 0-2.8 1.4 1.4 0 0 0 0 2.8Z",
  trending: "M2.5 11.5 6 8l2.3 2.3L13.5 5M10.5 5h3v3",
  file: "M9.5 2.5H5a1 1 0 0 0-1 1v9a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V5L9.5 2.5ZM9.3 2.6V5H12",
  quote:
    "M5.5 5.5c-1.4 0-2.2 1-2.2 2.2 0 1.1.8 1.8 1.7 1.8.8 0 1.4-.5 1.4-1.3 0-.7-.5-1.2-1.1-1.2M11.5 5.5c-1.4 0-2.2 1-2.2 2.2 0 1.1.8 1.8 1.7 1.8.8 0 1.4-.5 1.4-1.3 0-.7-.5-1.2-1.1-1.2",
  mic: "M8 9.5a2 2 0 0 0 2-2V4a2 2 0 1 0-4 0v3.5a2 2 0 0 0 2 2ZM4.5 7.5A3.5 3.5 0 0 0 11.5 7.5M8 11.5v2",
  external: "M9 3.5h3.5V7M12.2 3.8 7.5 8.5M11 9.5v2.8a1 1 0 0 1-1 1H3.7a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h2.8",
  sun: "M8 10.8a2.8 2.8 0 1 0 0-5.6 2.8 2.8 0 0 0 0 5.6ZM8 1.6v1.5M8 12.9v1.5M2.9 2.9l1.1 1.1M12 12l1.1 1.1M1.6 8h1.5M12.9 8h1.5M2.9 13.1 4 12M12 4l1.1-1.1",
};

interface IconProps {
  name: IconName;
  size?: number;
  /** Give the icon an accessible name; only for icon-only controls. */
  title?: string;
  className?: string;
}

export function Icon({ name, size = 16, title, className }: IconProps) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
      aria-label={title}
      focusable="false"
    >
      {title ? <title>{title}</title> : null}
      <path d={PATHS[name]} />
    </svg>
  );
}
