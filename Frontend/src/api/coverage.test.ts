/**
 * Does the frontend cover the backend's API?
 *
 * The backend's route list is read from the FastAPI source, so adding an
 * endpoint there and forgetting it here shows up as a failing test rather than
 * as a feature nobody can reach. That is how `POST /hiring/.../screen` went
 * missing: it is the step that turns a scored candidate into a decided one, so
 * without it a candidate could never progress, and nothing flagged it.
 *
 * Every backend endpoint is now reachable from one of the two frontends, so
 * the exemption list is empty. Anything added to it must carry a reason, and a
 * stale entry fails the test too.
 */

import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const REPO = join(__dirname, "..", "..", "..");
const ROUTES_DIR = join(REPO, "app", "routes");

const CLIENT = readFileSync(join(__dirname, "client.ts"), "utf8");

/** The candidate-facing recorder is a separate, plain-HTML app. */
const RECORDER = readFileSync(
  join(REPO, "app", "static", "interview.html"),
  "utf8",
);

interface Route {
  method: string;
  path: string;
  file: string;
}

/** Read `@router.<method>("<path>")` plus each router's prefix. */
function backendRoutes(): Route[] {
  const routes: Route[] = [];

  for (const file of readdirSync(ROUTES_DIR).filter((f) => f.endsWith(".py"))) {
    const source = readFileSync(join(ROUTES_DIR, file), "utf8");

    const prefix = source.match(/prefix\s*=\s*"([^"]*)"/)?.[1] ?? "";

    for (const match of source.matchAll(
      /@router\.(get|post|put|patch|delete)\(\s*\n?\s*"([^"]*)"/g,
    )) {
      routes.push({
        method: match[1]!.toUpperCase(),
        path: prefix + match[2]!,
        file,
      });
    }
  }

  return routes;
}

/**
 * Endpoints no frontend calls, each with the reason.
 *
 * Empty on purpose: the frontend covers the whole API. Adding an entry here is
 * a deliberate decision that has to be justified in writing.
 */
const INTENTIONALLY_UNUSED: Record<string, string> = {};

/** Turn a route into the literal the client would contain. */
function clientPattern(path: string): RegExp {
  const escaped = path
    .replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
    // `{candidate_id}` becomes `${candidateId}` in a template literal
    .replace(/\\\{[a-z_]+\\\}/g, "\\$\\{[^}]+\\}");

  return new RegExp(escaped);
}

describe("backend coverage", () => {
  const routes = backendRoutes();

  it("finds the backend's routes", () => {
    // A parser that silently matches nothing would make every test below pass.
    expect(routes.length).toBeGreaterThan(15);
    expect(routes.map((r) => `${r.method} ${r.path}`)).toContain(
      "GET /applications/",
    );
  });

  it("reaches every endpoint from the dashboard or the recorder", () => {
    const uncovered: string[] = [];

    for (const { method, path } of routes) {
      const key = `${method} ${path}`;

      if (key in INTENTIONALLY_UNUSED) continue;

      const pattern = clientPattern(path);

      if (pattern.test(CLIENT) || pattern.test(RECORDER)) continue;

      uncovered.push(key);
    }

    expect(uncovered).toEqual([]);
  });

  it("documents a reason for each endpoint it skips", () => {
    const known = new Set(routes.map((r) => `${r.method} ${r.path}`));

    // A stale exemption hides a route that has since been removed or renamed.
    const stale = Object.keys(INTENTIONALLY_UNUSED).filter(
      (key) => !known.has(key),
    );

    expect(stale).toEqual([]);

    for (const reason of Object.values(INTENTIONALLY_UNUSED)) {
      expect(reason.length).toBeGreaterThan(20);
    }
  });

  it("calls the screening decision, which a candidate cannot progress without", () => {
    expect(CLIENT).toContain("/hiring/candidates/");
    expect(CLIENT).toContain("screenCandidate");
  });
});

describe("client methods are actually used", () => {
  /**
   * The gap this closes: `updateJob` and `getJob` existed in the client for a
   * whole feature, satisfying the coverage test above, while no component
   * called either. A method nothing calls is not a feature, and the test that
   * only read the client could not tell the difference.
   */
  const SOURCE_DIR = join(__dirname, "..");

  function sourceFiles(dir: string): string[] {
    return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
      const path = join(dir, entry.name);

      if (entry.isDirectory()) {
        return entry.name === "test" ? [] : sourceFiles(path);
      }

      if (!/\.(ts|tsx)$/.test(entry.name)) return [];
      if (/\.test\.(ts|tsx)$/.test(entry.name)) return [];
      if (path === join(SOURCE_DIR, "api", "client.ts")) return [];

      return [path];
    });
  }

  /** Method names declared on the exported `api` object. */
  function clientMethods(): string[] {
    const body = CLIENT.slice(CLIENT.indexOf("export const api = {"));

    return [...body.matchAll(/^\s{2}([a-zA-Z][a-zA-Z0-9]*):/gm)].map(
      (match) => match[1]!,
    );
  }

  it("finds the client's methods", () => {
    const methods = clientMethods();

    expect(methods.length).toBeGreaterThan(10);
    expect(methods).toContain("listJobs");
  });

  it("has a caller for every client method", () => {
    const sources = sourceFiles(SOURCE_DIR)
      .map((path) => readFileSync(path, "utf8"))
      .join("\n");

    const unused = clientMethods().filter(
      (method) => !sources.includes(`api.${method}`),
    );

    expect(unused).toEqual([]);
  });
});
