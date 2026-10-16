/** Formatting helpers. Kept out of component files so fast refresh works. */

/**
 * Parse a timestamp from the API.
 *
 * The backend stores and returns *naive UTC* (`2026-12-01T23:59:00`, no
 * designator), but JavaScript parses a string without one as local time. On a
 * UTC+05:45 machine that is a 5h45m error, enough to show the wrong day for a
 * deadline — so the designator is added when it is missing.
 */
export function parseApiDate(value: string | null | undefined): Date | null {
  if (!value) return null;

  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value);

  const date = new Date(hasZone ? value : `${value}Z`);

  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDate(value: string | null | undefined): string {
  const date = parseApiDate(value);

  if (!date) return "--";

  return date.toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/** A deadline needs its time as well as its date, in the viewer's zone. */
export function formatDateTime(value: string | null | undefined): string {
  const date = parseApiDate(value);

  if (!date) return "--";

  return date.toLocaleString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * An API timestamp as a value for `<input type="datetime-local">`.
 *
 * The input works in the viewer's local time, so the UTC instant is shifted
 * into local before being formatted — otherwise a recruiter in Kathmandu would
 * see 23:59 and mean 05:44.
 */
export function toLocalInput(value: string | null | undefined): string {
  const date = parseApiDate(value);

  if (!date) return "";

  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);

  return local.toISOString().slice(0, 16);
}

/** The inverse: a local datetime-local value as a UTC instant for the API. */
export function fromLocalInput(value: string): string | null {
  if (!value) return null;

  // `new Date` reads a value with no designator as local, which is what the
  // input means here.
  const date = new Date(value);

  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

export function formatSeconds(total: number | null | undefined): string {
  if (total === null || total === undefined) return "--";

  const minutes = Math.floor(total / 60);
  const seconds = Math.round(total % 60);

  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

/** Turns `technical_depth` into `Technical depth`. */
export function humanise(value: string | null | undefined): string {
  if (!value) return "--";

  const spaced = value.replace(/_/g, " ");

  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

export function initials(name: string | null | undefined): string {
  if (!name) return "--";

  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]!.toUpperCase())
    .join("");
}
