/**
 * How AI output is presented.
 *
 * The product rule these components encode: the model produces a
 * *recommendation with evidence*, never a decision. So every one of them
 *
 *   - says that a number came from AI, and from which model,
 *   - shows the quote the score rests on, and whether that quote was
 *     verified against the transcript,
 *   - surfaces what the system is unsure about instead of hiding it,
 *   - and never conveys a state by colour alone.
 *
 * A score whose evidence could not be verified is shown as *unverified*
 * rather than quietly dropped, because an unverifiable quote means the score
 * behind it cannot be defended.
 */

import type { ReactNode } from "react";
import { Icon } from "./Icon";
import type {
  AnswerScore,
  CompetencyScore,
  Scorecard,
} from "../types";
import { ProgressBar } from "./primitives";
import { humanise } from "../lib/format";
import { flagLabel } from "../lib/flags";

/* -------------------------------------------------- flag explanations */

/**
 * Flags are written for a recruiter, not a developer: each says what happened
 * and what it means for the score.
 */

export function FlagList({ flags }: { flags: string[] }) {
  if (flags.length === 0) return null;

  return (
    <ul className="skill-list" style={{ marginTop: 8 }}>
      {flags.map((flag) => (
        <li
          key={flag}
          className="skill-chip"
          style={{ background: "#fff2dc", color: "#a9751c" }}
        >
          {flagLabel(flag)}
        </li>
      ))}
    </ul>
  );
}

/* ---------------------------------------------------------- the score */

/**
 * The headline AI score.
 *
 * It is deliberately labelled as a recommendation, states the scale, and
 * carries a sentence saying it is not a decision. `aria-label` spells the
 * number out, because "3.4" on its own tells a screen-reader user nothing.
 */
export function AiScoreBlock({
  scorecard,
  model,
}: {
  scorecard: Scorecard;
  model?: string | null;
}) {
  const { overall_score, scale, answers_scored, questions_total } = scorecard;

  const hasScore = overall_score !== null;

  return (
    <div className="score-block">
      <div>
        <p className="eyebrow">AI RECOMMENDATION</p>
        <p
          className="score-big"
          aria-label={
            hasScore
              ? `AI recommended score ${overall_score} out of ${scale.max}`
              : "No AI score available"
          }
        >
          {hasScore ? overall_score.toFixed(1) : "--"}
          <span> / {scale.max}</span>
        </p>
      </div>
      <div className="score-caption">
        <strong>
          {hasScore
            ? `Based on ${answers_scored} of ${questions_total} answers`
            : "Not enough answers to score"}
        </strong>
        <p>
          This is a suggestion from {model ? `the ${model} model` : "the model"},
          not a decision. Every score below shows the candidate's own words that
          it was based on. You make the final call.
        </p>
      </div>
    </div>
  );
}

/* ------------------------------------------------------ one competency */

export function CompetencyRow({
  competency,
  scale,
}: {
  competency: CompetencyScore;
  scale: { min: number; max: number };
}) {
  const { name, score, weight, answers_scored, answers_total } = competency;

  const scored = score !== null;

  return (
    <div style={{ padding: "14px 0", borderBottom: "1px solid #f0f2f7" }}>
      <div className="pipeline-stage-top">
        <span>
          {name}
          <span className="table-subtext">
            Weight {Math.round(weight * 100)}% · {answers_scored} of{" "}
            {answers_total} answered
          </span>
        </span>
        <strong>
          {scored ? `${score.toFixed(1)}/${scale.max}` : "Not scored"}
        </strong>
      </div>

      <ProgressBar
        value={scored ? score : 0}
        max={scale.max}
        tone={scored ? (score >= 4 ? "teal" : score >= 3 ? "blue" : "amber") : "amber"}
        label={`${name}: ${scored ? `${score} out of ${scale.max}` : "not scored"}`}
      />

      <FlagList flags={competency.flags} />
    </div>
  );
}

/* --------------------------------------------------------- evidence */

/**
 * The quote a score rests on.
 *
 * A verified quote gets the tick treatment; an unverified or missing one gets
 * the warning treatment *and* says so in words.
 */
export function EvidenceItem({
  score,
  scale,
}: {
  score: AnswerScore;
  scale: { min: number; max: number };
}) {
  const verified = score.quote_verified && score.evidence_quote.length > 0;

  return (
    <li className="evidence-item">
      <span className={verified ? "evidence-check" : "evidence-neutral"}>
        <Icon name={verified ? "check" : "alert"} size={13} />
      </span>
      <div>
        <strong>
          {humanise(score.competency)}
          {score.score !== null ? ` — ${score.score}/${scale.max}` : " — not scored"}
        </strong>

        {score.evidence_quote ? (
          <p>
            <q>{score.evidence_quote}</q>
          </p>
        ) : (
          <p>No supporting quote was given.</p>
        )}

        {score.reasoning ? (
          <span className="evidence-source">{score.reasoning}</span>
        ) : null}

        <span className="evidence-source">
          {verified
            ? "Quote verified against the transcript."
            : score.evidence_quote
              ? "This quote could not be found in the transcript."
              : "Score not backed by a quote."}
          {score.question_text ? ` Question: ${score.question_text}` : ""}
        </span>

        <FlagList flags={score.flags} />
      </div>
    </li>
  );
}

export function EvidenceList({
  scores,
  scale,
}: {
  scores: AnswerScore[];
  scale: { min: number; max: number };
}) {
  return (
    <ul className="evidence-list" style={{ listStyle: "none", padding: 0, margin: 0 }}>
      {scores.map((score) => (
        <EvidenceItem key={score.question_id} score={score} scale={scale} />
      ))}
    </ul>
  );
}

/* ------------------------------------------------------ review banner */

/**
 * Shown when the system itself says a human should look.
 *
 * `role="alert"` so it is announced the moment a scorecard loads flagged;
 * this is the one piece of AI output a reviewer must not miss.
 */
export function ReviewBanner({ scorecard }: { scorecard: Scorecard }) {
  if (!scorecard.needs_human_review) {
    return (
      <div className="notice">
        <Icon name="check" size={17} />
        <div>
          <strong>Nothing flagged for review</strong>
          <p>
            Every question was answered and scored with a verified supporting
            quote. Read the evidence below before deciding.
          </p>
        </div>
      </div>
    );
  }

  const reasons = [...new Set(scorecard.review_items.flatMap((item) => item.flags))];

  return (
    <div className="notice" role="alert" style={{ background: "#fff8ec", borderColor: "#f3e2c4", color: "#8a5e11" }}>
      <Icon name="alert" size={17} />
      <div>
        <strong>Needs a human look</strong>
        <p>
          {scorecard.review_items.length} of {scorecard.questions_total}{" "}
          {scorecard.review_items.length === 1 ? "answer" : "answers"} could not
          be scored reliably. Check these before deciding:
        </p>
        <ul style={{ margin: "8px 0 0", paddingLeft: 16 }}>
          {reasons.map((flag) => (
            <li key={flag} style={{ fontSize: 10, lineHeight: 1.6, color: "#6f7195" }}>
              {flagLabel(flag)}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

/* ------------------------------------------------------- how it added up */

/** The weighting, written out so a reviewer can redo the sum by hand. */
export function WeightingDisclosure({ scorecard }: { scorecard: Scorecard }) {
  const { weighting, competency_scores, overall_score, scale } = scorecard;

  const used = competency_scores.filter((entry) => entry.score !== null);

  return (
    <details style={{ marginTop: 14 }}>
      <summary
        className="text-button"
        style={{ cursor: "pointer", listStyle: "none" }}
      >
        How was this calculated?
      </summary>
      <div style={{ marginTop: 10 }}>
        <p className="muted">{weighting.note}</p>
        <table>
          <caption className="sr-only">
            Each competency score and the weight applied to it
          </caption>
          <thead>
            <tr>
              <th scope="col">Competency</th>
              <th scope="col">Score</th>
              <th scope="col">Weight</th>
              <th scope="col">Contribution</th>
            </tr>
          </thead>
          <tbody>
            {used.map((entry) => {
              const weight = weighting.weights[entry.competency] ?? 0;

              return (
                <tr key={entry.competency}>
                  <td>{entry.name}</td>
                  <td>
                    {entry.score!.toFixed(1)}/{scale.max}
                  </td>
                  <td>{Math.round(weight * 100)}%</td>
                  <td>{(entry.score! * weight).toFixed(2)}</td>
                </tr>
              );
            })}
            <tr>
              <td>
                <strong>Overall</strong>
              </td>
              <td colSpan={2} />
              <td>
                <strong>
                  {overall_score !== null ? overall_score.toFixed(2) : "--"}
                </strong>
              </td>
            </tr>
          </tbody>
        </table>

        {weighting.excluded.length > 0 ? (
          <p className="table-note">
            Excluded from the total because they could not be scored:{" "}
            {weighting.excluded.map(humanise).join(", ")}. Their weight was
            shared across the competencies above.
          </p>
        ) : null}
      </div>
    </details>
  );
}

/* --------------------------------------------------------- the rubric */

/** The written standard behind the numbers. */
export function RubricDisclosure({ scorecard }: { scorecard: Scorecard }) {
  return (
    <details style={{ marginTop: 10 }}>
      <summary
        className="text-button"
        style={{ cursor: "pointer", listStyle: "none" }}
      >
        Show the scoring rubric
      </summary>
      <div style={{ marginTop: 10 }}>
        {scorecard.rubric.map((entry) => (
          <div key={entry.competency} style={{ marginBottom: 14 }}>
            <strong style={{ fontSize: 11, color: "#2a3653" }}>
              {entry.name}{" "}
              <span className="muted">({Math.round(entry.weight * 100)}%)</span>
            </strong>
            <dl style={{ margin: "6px 0 0" }}>
              {Object.entries(entry.descriptors)
                .sort(([a], [b]) => Number(a) - Number(b))
                .map(([level, text]) => (
                  <div key={level} style={{ display: "flex", gap: 8, marginTop: 4 }}>
                    <dt
                      className="match-number"
                      style={{ minWidth: 22, height: 20, fontSize: 10 }}
                    >
                      {level}
                    </dt>
                    <dd className="muted" style={{ margin: 0, fontSize: 10 }}>
                      {text}
                    </dd>
                  </div>
                ))}
            </dl>
          </div>
        ))}
      </div>
    </details>
  );
}

/* ------------------------------------------------- screening rationale */

/** The pre-interview screening score, with the same honesty rules. */
export function ScreeningBreakdown({
  score,
  semantic,
  skill,
  experience,
  matched,
  missing,
  rationale,
}: {
  score: number | null;
  semantic: number | null;
  skill: number | null;
  experience: number | null;
  matched: string[];
  missing: string[];
  rationale: string | null;
}) {
  const parts: { label: string; value: number | null; tone: "blue" | "violet" | "teal" }[] = [
    { label: "Resume–role similarity", value: semantic, tone: "blue" },
    { label: "Required skills matched", value: skill, tone: "violet" },
    { label: "Experience vs minimum", value: experience, tone: "teal" },
  ];

  return (
    <>
      <div className="score-block">
        <div>
          <p className="eyebrow">SCREENING SCORE</p>
          <p
            className="score-big"
            aria-label={
              score !== null
                ? `Screening score ${score} out of 100`
                : "Not yet screened"
            }
          >
            {score !== null ? score.toFixed(1) : "--"}
            <span> / 100</span>
          </p>
        </div>
        <div className="score-caption">
          <strong>Computed from the resume, not a judgement of the person</strong>
          <p>
            {rationale ??
              "This candidate has not been screened yet, so there is no score to explain."}
          </p>
        </div>
      </div>

      {parts.map((part) => (
        <div key={part.label} style={{ padding: "12px 0" }}>
          <div className="pipeline-stage-top">
            <span>{part.label}</span>
            <strong>{part.value !== null ? `${Math.round(part.value)}%` : "--"}</strong>
          </div>
          <ProgressBar
            value={part.value ?? 0}
            tone={part.tone}
            label={`${part.label}: ${part.value !== null ? `${Math.round(part.value)} percent` : "not available"}`}
          />
        </div>
      ))}

      {matched.length > 0 || missing.length > 0 ? (
        <div style={{ marginTop: 14 }}>
          {matched.length > 0 ? (
            <>
              <h3>Skills matched</h3>
              <SkillChips skills={matched} tone="match" />
            </>
          ) : null}
          {missing.length > 0 ? (
            <>
              <h3>Required skills not found in the resume</h3>
              <SkillChips skills={missing} tone="missing" />
              <p className="table-note">
                Missing from the resume text only. A skill the candidate has but
                did not write down will show here.
              </p>
            </>
          ) : null}
        </div>
      ) : null}
    </>
  );
}

export function SkillChips({
  skills,
  tone = "match",
}: {
  skills: string[];
  tone?: "match" | "missing" | "neutral";
}) {
  const style =
    tone === "missing"
      ? { background: "#fff2dc", color: "#a9751c" }
      : tone === "neutral"
        ? undefined
        : { background: "#e2f7ef", color: "#128268" };

  return (
    <ul className="skill-list" style={{ listStyle: "none", padding: 0, margin: 0 }}>
      {skills.map((skill) => (
        <li key={skill} className="skill-chip" style={style}>
          {skill}
        </li>
      ))}
    </ul>
  );
}

/** A compact score cell for tables, with the scale spelled out for AT. */
export function ScoreCell({
  value,
  max = 100,
  caption,
}: {
  value: number | null;
  max?: number;
  caption?: string;
}): ReactNode {
  if (value === null) {
    return (
      <span className="muted" title="Not scored yet">
        --
      </span>
    );
  }

  return (
    <>
      <span
        className="match-number"
        aria-label={`${value} out of ${max}`}
      >
        {max === 100 ? Math.round(value) : value.toFixed(1)}
      </span>
      {caption ? <span className="table-subtext">{caption}</span> : null}
    </>
  );
}
