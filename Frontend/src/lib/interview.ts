/**
 * The interview template's shape, as the backend defines it.
 *
 * These mirror `app/services/interview_questions.py` and
 * `app/services/rubric.py`. They are duplicated here rather than fetched
 * because there is no endpoint that exposes the rubric on its own; if that
 * changes, this file is the single place to replace.
 */

/** Seconds of thinking time before each question records. */
export const PREPARATION_SECONDS = 30;

/** Used by the backend when a question omits its limit. */
export const DEFAULT_TIME_LIMIT_SECONDS = 90;

/**
 * The competencies the default rubric scores, with their weights.
 *
 * A question tagged with anything else is still scored, but against the
 * general row — so the editor warns rather than silently diverging.
 */
export const COMPETENCY_OPTIONS = [
  {
    id: "technical_depth",
    label: "Technical depth",
    weight: 0.35,
    hint: "First-hand knowledge of the tools the role uses",
  },
  {
    id: "system_design",
    label: "System design",
    weight: 0.35,
    hint: "Shaping a system, and reasoning about scale and failure",
  },
  {
    id: "problem_solving",
    label: "Problem-solving approach",
    weight: 0.3,
    hint: "Framing an unfamiliar problem and verifying a solution",
  },
  {
    id: "general",
    label: "General response quality",
    weight: 0.2,
    hint: "Whether the answer addresses the question at all",
  },
] as const;

export type CompetencyId = (typeof COMPETENCY_OPTIONS)[number]["id"];

/** Limits offered in the editor. Any integer is accepted by the API. */
export const TIME_LIMIT_OPTIONS = [30, 45, 60, 90, 120, 180, 240];

export interface QuestionDraft {
  /** Local only, for list keys; the API derives its own ids. */
  key: string;
  text: string;
  competency: CompetencyId;
  time_limit_seconds: number;
}

let nextKey = 0;

export function blankQuestion(
  competency: CompetencyId = "technical_depth",
): QuestionDraft {
  nextKey += 1;

  return {
    key: `q-${nextKey}`,
    text: "",
    competency,
    time_limit_seconds: DEFAULT_TIME_LIMIT_SECONDS,
  };
}

/** The backend's own default set, as a starting point to edit. */
export function defaultTemplate(): QuestionDraft[] {
  return [
    {
      text: "Tell us about your backend development experience.",
      competency: "technical_depth" as CompetencyId,
      time_limit_seconds: 60,
    },
    {
      text: "How would you design a scalable REST API?",
      competency: "system_design" as CompetencyId,
      time_limit_seconds: 90,
    },
    {
      text: "Describe a challenging technical problem you solved.",
      competency: "problem_solving" as CompetencyId,
      time_limit_seconds: 120,
    },
  ].map((question) => {
    nextKey += 1;

    return { key: `q-${nextKey}`, ...question };
  });
}

/** Total time an interview costs a candidate, preparation included. */
export function candidateTimeSeconds(questions: QuestionDraft[]): number {
  return questions.reduce(
    (total, question) =>
      total + question.time_limit_seconds + PREPARATION_SECONDS,
    0,
  );
}

/** Which rubric competencies no question covers. */
export function uncoveredCompetencies(
  questions: QuestionDraft[],
): typeof COMPETENCY_OPTIONS[number][] {
  const used = new Set(questions.map((question) => question.competency));

  return COMPETENCY_OPTIONS.filter(
    (option) => option.id !== "general" && !used.has(option.id),
  );
}
