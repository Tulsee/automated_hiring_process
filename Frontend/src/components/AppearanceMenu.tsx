/**
 * Theme and text-size picker for the topbar.
 *
 * The theme list is a `radiogroup` because exactly one applies; the sizes are
 * toggle buttons with `aria-pressed`. Each theme shows a two-tone dot, so the
 * choice is previewable rather than guessed from a word.
 */

import { useEffect, useRef, useState } from "react";
import { Icon } from "./Icon";
import {
  TEXT_SIZES,
  THEMES,
  type TextSizeId,
  type ThemeId,
} from "../hooks/useTheme";

interface AppearanceMenuProps {
  theme: ThemeId;
  onThemeChange: (theme: ThemeId) => void;
  textSize: TextSizeId;
  onTextSizeChange: (size: TextSizeId) => void;
  /** "sidebar" opens the panel upward, since the trigger sits at the bottom. */
  placement?: "sidebar" | "topbar";
}

export function AppearanceMenu({
  theme,
  onThemeChange,
  textSize,
  onTextSizeChange,
  placement = "sidebar",
}: AppearanceMenuProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  // Close on an outside click or Escape, and hand focus back to the trigger so
  // a keyboard user is not dropped at the top of the page.
  useEffect(() => {
    if (!open) return;

    function onPointerDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        buttonRef.current?.focus();
      }
    }

    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);

    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div
      className={`appearance appearance--${placement}`}
      ref={containerRef}
    >
      <button
        type="button"
        className="icon-button"
        ref={buttonRef}
        aria-expanded={open}
        aria-haspopup="true"
        onClick={() => setOpen((value) => !value)}
      >
        <Icon name="sun" size={17} title="Appearance" />
      </button>

      {open ? (
        <div className="appearance-panel">
          <h3 id="theme-label">Theme</h3>
          <div role="radiogroup" aria-labelledby="theme-label">
            {THEMES.map((entry) => (
              <button
                key={entry.id}
                type="button"
                role="radio"
                aria-checked={theme === entry.id}
                className="appearance-option"
                onClick={() => onThemeChange(entry.id)}
              >
                <span
                  className={`theme-dot theme-dot--${entry.id}`}
                  aria-hidden="true"
                />
                <span>
                  {entry.label}
                  <small>{entry.hint}</small>
                </span>
                {theme === entry.id ? <Icon name="check" size={13} /> : null}
              </button>
            ))}
          </div>

          <h3 id="size-label">Text size</h3>
          <div className="size-row" role="group" aria-labelledby="size-label">
            {TEXT_SIZES.map((entry) => (
              <button
                key={entry.id}
                type="button"
                aria-pressed={textSize === entry.id}
                onClick={() => onTextSizeChange(entry.id)}
              >
                {entry.label}
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
