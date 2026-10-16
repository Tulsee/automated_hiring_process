/** Formatting helpers. Kept out of component files so fast refresh works. */

export function formatDate(value: string | null | undefined): string {
  if (!value) return "--";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "--";

  return date.toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
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
