/**
 * Contract tests for the stylesheet.
 *
 * These exist because two rendering bugs got through review: the topbar kept a
 * literal white background so it stayed white in dark themes, and several
 * sidebar text colours were mapped to tokens that flip dark — making the
 * sidebar unreadable on a dark theme. Both are structural properties of the
 * CSS, so they can be asserted without a browser.
 */

import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const CSS = readFileSync(join(__dirname, "styles.css"), "utf8");

const THEMES = ["dark", "midnight", "warm", "contrast"] as const;

/** The declarations inside a block, as {token: value}. */
function tokensOf(pattern: RegExp): Record<string, string> {
  const match = CSS.match(pattern);

  if (!match) return {};

  return Object.fromEntries(
    [...match[1]!.matchAll(/--([a-z0-9-]+):\s*([^;]+);/g)].map((m) => [
      m[1]!,
      m[2]!.trim(),
    ]),
  );
}

const ROOT = tokensOf(/^:root \{([\s\S]*?)\n\}/m);

/** Selectors that sit on the sidebar or promo panel, navy in every theme. */
const ALWAYS_DARK = [
  ".sidebar",
  ".brand",
  ".nav-item",
  ".workspace-label",
  ".sidebar-help",
  ".sidebar-user",
  ".sidebar-close",
  ".help-icon",
  ".ai-promo",
  ".promo-icon",
  ".avatar--sidebar",
];

/** Tokens whose lightness inverts between the light and dark themes. */
const FLIPPING = [
  "text",
  "text-strong",
  "text-muted",
  "text-faint",
  "surface",
  "surface-2",
  "surface-3",
  "bg",
  "blue-ink",
  "blue-soft",
  "violet-soft",
  "teal-soft",
  "amber-soft",
];

interface Rule {
  selector: string;
  body: string;
}

const RULES: Rule[] = [...CSS.matchAll(/(?:^|\n)([^{}@/][^{}]*?)\{([^}]*)\}/g)].map(
  (m) => ({ selector: m[1]!.replace(/\s+/g, " ").trim(), body: m[2]! }),
);

describe("token coverage", () => {
  it("defines every token it references", () => {
    const used = new Set(
      [...CSS.matchAll(/var\(--([a-z0-9-]+)\)/g)].map((m) => m[1]!),
    );
    const defined = new Set(
      [...CSS.matchAll(/^\s*--([a-z0-9-]+):/gm)].map((m) => m[1]!),
    );

    expect([...used].filter((token) => !defined.has(token))).toEqual([]);
  });

  it("has a light value for every token the themes override", () => {
    for (const theme of THEMES) {
      const themed = tokensOf(
        new RegExp(`\\[data-theme="${theme}"\\] \\{([\\s\\S]*?)\\n\\}`),
      );

      const missing = Object.keys(themed).filter((token) => !(token in ROOT));

      expect(missing, `${theme} overrides tokens absent from :root`).toEqual(
        [],
      );
    }
  });

  it("balances its braces", () => {
    expect((CSS.match(/\{/g) ?? []).length).toBe(
      (CSS.match(/\}/g) ?? []).length,
    );
  });
});

describe("themes", () => {
  it.each(THEMES)("defines the %s theme", (theme) => {
    expect(CSS).toContain(`[data-theme="${theme}"]`);
  });

  it("follows the OS preference when no theme is chosen", () => {
    expect(CSS).toMatch(
      /@media \(prefers-color-scheme: dark\)[\s\S]*?:root:not\(\[data-theme\]\)/,
    );
  });

  it("declares color-scheme per theme, so native controls follow", () => {
    expect(ROOT["color-scheme"] ?? "light").toBeTruthy();

    for (const theme of THEMES) {
      const block = CSS.match(
        new RegExp(`\\[data-theme="${theme}"\\] \\{([\\s\\S]*?)\\n\\}`),
      )![1]!;

      expect(block, theme).toContain("color-scheme");
    }
  });

  it("gives every theme its own surfaces and text", () => {
    for (const theme of THEMES) {
      const themed = tokensOf(
        new RegExp(`\\[data-theme="${theme}"\\] \\{([\\s\\S]*?)\\n\\}`),
      );

      for (const token of ["bg", "surface", "text-strong", "text-muted"]) {
        expect(themed[token], `${theme} must override --${token}`).toBeTruthy();
      }

      // High contrast keeps a white surface on purpose, so it is the ink that
      // has to differ from the light theme.
      expect(themed["text-strong"], theme).not.toBe(ROOT["text-strong"]);
    }
  });

  it("themes the translucent topbar, so it cannot stay white on dark", () => {
    // The bug this guards: `.topbar { background: #ffffffed }`.
    expect(ROOT["surface-translucent"]).toBeTruthy();

    for (const theme of THEMES) {
      const themed = tokensOf(
        new RegExp(`\\[data-theme="${theme}"\\] \\{([\\s\\S]*?)\\n\\}`),
      );

      expect(
        themed["surface-translucent"],
        `${theme} must theme the topbar`,
      ).toBeTruthy();
    }
  });
});

describe("no hardcoded colours outside the always-dark panels", () => {
  const SIDEBAR_SCOPED = /^(\.sidebar|\.brand|\.nav-|\.ai-promo|\.promo|\.help-icon|\.orb|\.avatar)/;

  it("uses a token for every background, including translucent ones", () => {
    // 8-digit hex is included deliberately: `.topbar` shipped with
    // `background: #ffffffed`, an almost-opaque white that stayed white in
    // every dark theme. An alpha channel does not make a colour safe.
    const offenders = RULES.flatMap(({ selector, body }) => {
      const matches = [
        ...body.matchAll(
          /background(?:-color)?:\s*(#[0-9a-fA-F]{3,8})\s*;/g,
        ),
      ];

      // The sidebar and promo panel are dark in every theme, so literal
      // values there are intentional.
      if (selector.split(",").some((s) => SIDEBAR_SCOPED.test(s.trim()))) {
        return [];
      }

      return matches.map((m) => `${selector} -> ${m[1]}`);
    });

    expect(offenders).toEqual([]);
  });

  it("uses a token for every text colour outside the dark panels", () => {
    const offenders = RULES.flatMap(({ selector, body }) => {
      const matches = [
        ...body.matchAll(/(?<!-)color:\s*(#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3}|white)\s*;/g),
      ].filter(
        // A translucent tint (8-digit hex) reads on a light or a dark
        // background, so decorative ones need no token.
        (m) => m[1]!.length !== 9,
      );

      if (
        selector.split(",").some((s) => SIDEBAR_SCOPED.test(s.trim())) ||
        selector.includes("--primary") ||
        selector.includes("--light")
      ) {
        return [];
      }

      return matches.map((m) => `${selector} -> ${m[1]}`);
    });

    expect(offenders).toEqual([]);
  });
});

describe("the always-dark panels stay readable in every theme", () => {
  it("never colours sidebar or promo text with a flipping token", () => {
    const offenders: string[] = [];

    for (const { selector, body } of RULES) {
      const parts = selector.split(",").map((s) => s.trim());

      // `.eyebrow` is used on light pages too and is overridden for the
      // sidebar separately.
      const inDarkScope = parts.some(
        (part) =>
          ALWAYS_DARK.some((prefix) => part.startsWith(prefix)) &&
          !part.endsWith(".eyebrow"),
      );

      if (!inDarkScope) continue;

      for (const [, token] of body.matchAll(
        /color:\s*var\(--([a-z0-9-]+)\)/g,
      )) {
        if (FLIPPING.includes(token!)) {
          offenders.push(`${selector} -> --${token}`);
        }
      }
    }

    // `.workspace-label, .eyebrow` is the shared base rule; the sidebar's
    // override follows it, so it is allowed here.
    const real = offenders.filter(
      (entry) => !entry.startsWith(".workspace-label, .eyebrow"),
    );

    expect(real).toEqual([]);
  });

  it("provides on-dark tokens that every theme leaves pale", () => {
    for (const token of ["on-dark", "on-dark-muted", "on-dark-faint"]) {
      expect(ROOT[token], `--${token} must exist`).toBeTruthy();
    }

    // No theme may redefine them, which is what keeps the sidebar readable.
    for (const theme of THEMES) {
      const themed = tokensOf(
        new RegExp(`\\[data-theme="${theme}"\\] \\{([\\s\\S]*?)\\n\\}`),
      );

      expect(themed["on-dark-muted"], `${theme} must not flip on-dark`).toBe(
        undefined,
      );
    }
  });
});

describe("the sidebar is themed, not merely tinted", () => {
  const SIDEBAR_TOKENS = [
    "sidebar-from",
    "sidebar-to",
    "sidebar-text",
    "sidebar-text-muted",
    "sidebar-text-faint",
    "sidebar-hover",
    "sidebar-line",
    "sidebar-avatar-bg",
    "sidebar-avatar-ink",
  ];

  it("declares the sidebar's own surface and text tokens", () => {
    for (const token of SIDEBAR_TOKENS) {
      expect(ROOT[token], `--${token} must exist`).toBeTruthy();
    }
  });

  it.each(THEMES)("gives %s its own sidebar", (theme) => {
    const themed = tokensOf(
      new RegExp(`\\[data-theme="${theme}"\\] \\{([\\s\\S]*?)\\n\\}`),
    );

    // The bug this guards: every theme produced a near-identical navy
    // sidebar, so switching themes looked like nothing happened.
    for (const token of SIDEBAR_TOKENS) {
      expect(themed[token], `${theme} must override --${token}`).toBeTruthy();
    }

    expect(themed["sidebar-from"], theme).not.toBe(ROOT["sidebar-from"]);
    expect(themed["sidebar-text-muted"], theme).not.toBe(
      ROOT["sidebar-text-muted"],
    );
  });

  it("paints the panel from the sidebar tokens, not the page's navy", () => {
    const rule = RULES.find((r) => r.selector === ".sidebar")!;

    expect(rule.body).toContain("var(--sidebar-from)");
    expect(rule.body).toContain("var(--sidebar-to)");
    expect(rule.body).not.toContain("var(--navy)");
  });

  it("uses no hardcoded white text on the sidebar panel itself", () => {
    // White text cannot follow a theme that makes the sidebar light. The
    // exceptions are elements filled with the brand violet — the mark and the
    // active nav item — where white is correct against the fill in every
    // theme, not against the panel.
    const ON_VIOLET = /\.brand-mark|\.nav-item--active|\.help-icon/;

    const offenders = RULES.filter(({ selector, body }) => {
      const parts = selector.split(",").map((part) => part.trim());

      if (parts.some((part) => ON_VIOLET.test(part))) return false;

      const inSidebar = parts.some((part) =>
        /^(\.sidebar|\.brand|\.nav-item|\.nav-count|\.workspace-label)/.test(
          part,
        ),
      );

      return (
        inSidebar && /(?<!-)color:\s*(#fff(?:fff)?|white)\s*;/.test(body)
      );
    }).map((r) => r.selector);

    expect(offenders).toEqual([]);
  });

  it("inverts the sidebar overlays through a token", () => {
    // A white wash is invisible on a light sidebar, so hover and dividers
    // have to be tokens too.
    const sidebarRules = RULES.filter(({ selector }) =>
      selector.split(",").some((part) => /^\.sidebar|^\.nav-/.test(part.trim())),
    );

    const literalOverlays = sidebarRules
      .filter(({ body }) => /#[0-9a-fA-F]{4}\b|#[0-9a-fA-F]{8}\b/.test(body))
      .map((r) => r.selector);

    expect(literalOverlays).toEqual([]);
  });
});

describe("the type scale", () => {
  it("routes every font size through --font-scale", () => {
    const unscaled = [
      ...CSS.matchAll(/font-size:\s*([\d.]+px)\s*;/g),
    ].map((m) => m[1]!);

    expect(unscaled).toEqual([]);
  });

  it("defaults to a scale above 1, because the base sizes are small", () => {
    expect(Number(ROOT["font-scale"])).toBeGreaterThan(1);
  });

  it("has no `font:` shorthand left, since calc inside it is unreliable", () => {
    const shorthands = [...CSS.matchAll(/^\s*font:\s*([^;]+);/gm)]
      .map((m) => m[1]!.trim())
      .filter((value) => value !== "inherit");

    expect(shorthands).toEqual([]);
  });

  it("keeps clamp() headlines responsive and scaled", () => {
    expect(CSS).toMatch(/clamp\(calc\([\d.]+px \* var\(--font-scale\)\)/);
  });
});

describe("accessibility affordances the design relies on", () => {
  it("keeps a visible focus ring", () => {
    expect(CSS).toMatch(/:focus-visible[\s\S]{0,200}outline:/);
  });

  it("preserves the pseudo-class selectors", () => {
    // A regex rewrite once turned `button:focus-visible` into
    // `button: focus-visible`, silently disabling focus styles.
    expect(CSS).toContain("button:focus-visible");
    expect(CSS).toContain("button:disabled");
    expect(CSS).not.toMatch(/^[a-z.#][^{};]*: (focus-visible|disabled|hover)/m);
  });

  it("honours prefers-reduced-motion", () => {
    expect(CSS).toContain("@media (prefers-reduced-motion: reduce)");
  });

  it("keeps a screen-reader-only utility", () => {
    expect(CSS).toMatch(/\.sr-only \{/);
  });
});
