import { useCallback, useEffect, useState } from "react";

/**
 * Theme and text-size preference.
 *
 * Both are written to `document.documentElement` — the theme as
 * `data-theme`, the size as the `--font-scale` custom property the stylesheet
 * multiplies every font size by — and persisted to localStorage so a reload
 * keeps the viewer's choice.
 *
 * "system" means *no* `data-theme` attribute, which lets the stylesheet's
 * `prefers-color-scheme` block apply. That is why it is the default: a viewer
 * whose OS is dark gets dark without having to ask.
 */

export const THEMES = [
  { id: "system", label: "System", hint: "Follow my device setting" },
  { id: "light", label: "Light", hint: "White and navy" },
  { id: "dark", label: "Dark", hint: "Neutral slate" },
  { id: "midnight", label: "Midnight", hint: "Deep navy" },
  { id: "warm", label: "Warm", hint: "Paper tones" },
  { id: "contrast", label: "High contrast", hint: "Maximum separation" },
] as const;

export type ThemeId = (typeof THEMES)[number]["id"];

export const TEXT_SIZES = [
  { id: "compact", label: "Compact", scale: 1 },
  { id: "default", label: "Default", scale: 1.15 },
  { id: "large", label: "Large", scale: 1.3 },
  { id: "larger", label: "Larger", scale: 1.45 },
] as const;

export type TextSizeId = (typeof TEXT_SIZES)[number]["id"];

const THEME_KEY = "hirewise.theme";
const SIZE_KEY = "hirewise.textSize";

function readStored<T extends string>(
  key: string,
  allowed: readonly { id: T }[],
  fallback: T,
): T {
  try {
    const stored = localStorage.getItem(key);

    if (stored && allowed.some((entry) => entry.id === stored)) {
      return stored as T;
    }
  } catch {
    // Private mode or blocked storage: fall back rather than fail.
  }

  return fallback;
}

export function useTheme() {
  const [theme, setThemeState] = useState<ThemeId>(() =>
    // Warm ("paper tones") is the default look; a viewer can still pick System,
    // Dark, etc. and that choice is remembered.
    readStored(THEME_KEY, THEMES, "warm"),
  );
  const [textSize, setTextSizeState] = useState<TextSizeId>(() =>
    readStored(SIZE_KEY, TEXT_SIZES, "default"),
  );

  // Applying to <html> rather than a React-owned node keeps the sidebar, the
  // scrollbar and the page background in the theme too.
  useEffect(() => {
    const root = document.documentElement;

    if (theme === "system") {
      root.removeAttribute("data-theme");
    } else {
      root.setAttribute("data-theme", theme);
    }
  }, [theme]);

  useEffect(() => {
    const scale =
      TEXT_SIZES.find((entry) => entry.id === textSize)?.scale ?? 1.15;

    document.documentElement.style.setProperty("--font-scale", String(scale));
  }, [textSize]);

  const setTheme = useCallback((next: ThemeId) => {
    setThemeState(next);

    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      // Not persisting is survivable; the choice still applies this session.
    }
  }, []);

  const setTextSize = useCallback((next: TextSizeId) => {
    setTextSizeState(next);

    try {
      localStorage.setItem(SIZE_KEY, next);
    } catch {
      /* as above */
    }
  }, []);

  return { theme, setTheme, textSize, setTextSize };
}
