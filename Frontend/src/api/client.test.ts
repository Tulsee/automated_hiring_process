/**
 * The fetch wrapper: URL building, and how backend errors become messages.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "./client";

/**
 * A stand-in for `fetch`.
 *
 * Typed with fetch's own signature so the recorded calls keep their argument
 * types, which is what lets the assertions below read the URL and the init.
 */
function respond(body: unknown, init: ResponseInit = {}) {
  return vi.fn<typeof fetch>(async () =>
    new Response(JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
      ...init,
    }),
  );
}

type FetchMock = ReturnType<typeof respond>;

function lastCall(mock: FetchMock) {
  const call = mock.mock.calls.at(-1);

  if (!call) throw new Error("fetch was never called");

  return { url: String(call[0]), init: call[1] ?? {} };
}

function lastUrl(mock: FetchMock) {
  return lastCall(mock).url;
}

describe("request building", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", respond([]));
  });

  it("uses relative paths, so the dev proxy and production agree", async () => {
    await api.listJobs();

    expect(lastUrl(fetch as unknown as FetchMock)).toBe("/jobs/");
  });

  it("omits empty filters from the query string", async () => {
    vi.stubGlobal("fetch", respond({ candidates: [] }));

    await api.listCandidates({ job_id: "", status: undefined, limit: 25 });

    const url = lastUrl(fetch as unknown as FetchMock);

    expect(url).toContain("limit=25");
    expect(url).not.toContain("job_id");
    expect(url).not.toContain("status");
  });

  it("passes every supported candidate filter", async () => {
    vi.stubGlobal("fetch", respond({ candidates: [] }));

    await api.listCandidates({
      job_id: "job-1",
      decision: "invited_to_interview",
      min_score: 50,
      sort: "recent",
      offset: 25,
    });

    const url = lastUrl(fetch as unknown as FetchMock);

    expect(url).toContain("job_id=job-1");
    expect(url).toContain("decision=invited_to_interview");
    expect(url).toContain("min_score=50");
    expect(url).toContain("sort=recent");
    expect(url).toContain("offset=25");
  });

  it("sends JSON for a created job", async () => {
    const mock = respond({});
    vi.stubGlobal("fetch", mock);

    await api.createJob({
      title: "SRE",
      description: "d",
      required_skills: ["linux"],
      minimum_experience: 1,
    });

    const { init } = lastCall(mock);

    expect(init.method).toBe("POST");
    expect(new Headers(init.headers).get("Content-Type")).toBe(
      "application/json",
    );
    expect(JSON.parse(init.body as string).title).toBe("SRE");
  });

  it("sends the resume as multipart, letting the browser set the boundary", async () => {
    const mock = respond({});
    vi.stubGlobal("fetch", mock);

    const file = new File(["cv"], "cv.pdf", { type: "application/pdf" });

    await api.applyToJob("job-1", file);

    const { init } = lastCall(mock);

    expect(init.body).toBeInstanceOf(FormData);
    // The wrapper always builds a Headers object, but with no Content-Type,
    // so the browser still sets the multipart boundary.
    expect(new Headers(init.headers).get("Content-Type")).toBeNull();
    expect((init.body as FormData).get("job_id")).toBe("job-1");
  });

  it("builds the answer video URL for the review player", () => {
    expect(api.answerVideoUrl("sess-1", "q_tech")).toBe(
      "/interviews/sess-1/questions/q_tech/answers",
    );
  });
});

describe("error handling", () => {
  it("surfaces FastAPI's detail string", async () => {
    vi.stubGlobal(
      "fetch",
      respond({ detail: "Candidate is not eligible" }, { status: 400 }),
    );

    await expect(api.createSession("cand-1")).rejects.toThrow(
      "Candidate is not eligible",
    );
  });

  it("surfaces a validation error's first message with its field", async () => {
    vi.stubGlobal(
      "fetch",
      respond(
        { detail: [{ loc: ["query", "limit"], msg: "must be >= 1" }] },
        { status: 422 },
      ),
    );

    await expect(api.listCandidates({ limit: 0 })).rejects.toThrow(
      "limit: must be >= 1",
    );
  });

  it("keeps the status code on the error", async () => {
    vi.stubGlobal("fetch", respond({ detail: "gone" }, { status: 410 }));

    await expect(api.getScorecard("sess-1")).rejects.toMatchObject({
      status: 410,
      name: "ApiError",
    });
  });

  it("explains a dead API rather than leaking a TypeError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
    );

    const error = await api.listJobs().catch((caught) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect(error.message).toMatch(/is the fastapi server running/i);
    expect(error.status).toBe(0);
  });

  it("copes with a non-JSON error body", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("<html>502</html>", { status: 502 })),
    );

    await expect(api.listJobs()).rejects.toThrow(/request failed \(502\)/i);
  });
});
