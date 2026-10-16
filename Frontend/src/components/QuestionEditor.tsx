/**
 * Where a recruiter writes the interview questions for a role.
 *
 * The questions are fixed per job rather than per candidate, which is what
 * makes scores comparable — so this is the one place they are decided, and the
 * editor surfaces the consequences of each choice:
 *
 *   - the competency a question is tagged with decides which rubric row scores
 *     it, so a competency no question covers is called out;
 *   - the time limit is the candidate's answering time, and each question also
 *     costs them 30 seconds of preparation, so the real total is shown.
 *
 * Leaving the list empty is valid: the backend falls back to its default
 * template, and the editor says so rather than quietly sending nothing.
 */

import { Icon } from "./Icon";
import { formatSeconds } from "../lib/format";
import {
  COMPETENCY_OPTIONS,
  PREPARATION_SECONDS,
  TIME_LIMIT_OPTIONS,
  type QuestionDraft,
  blankQuestion,
  candidateTimeSeconds,
  defaultTemplate,
  uncoveredCompetencies,
} from "../lib/interview";

export function QuestionEditor({
  questions,
  onChange,
}: {
  questions: QuestionDraft[];
  onChange: (questions: QuestionDraft[]) => void;
}) {
  function update(key: string, patch: Partial<QuestionDraft>) {
    onChange(
      questions.map((question) =>
        question.key === key ? { ...question, ...patch } : question,
      ),
    );
  }

  const uncovered = uncoveredCompetencies(questions);

  return (
    <fieldset className="question-editor">
      <legend>Interview questions</legend>

      {questions.length === 0 ? (
        <p className="muted">
          No questions yet. Every candidate for this role answers the same
          ones, in order. Leave this empty and the default set of three is used.
        </p>
      ) : null}

      {questions.map((question, index) => (
        <div className="question-row" key={question.key}>
          <div className="question-row-top">
            <strong>Question {index + 1}</strong>
            <button
              type="button"
              className="text-button"
              aria-label={`Remove question ${index + 1}`}
              onClick={() =>
                onChange(questions.filter((entry) => entry.key !== question.key))
              }
            >
              <Icon name="close" size={12} /> Remove
            </button>
          </div>

          <label>
            <span className="sr-only">Question {index + 1} text</span>
            <textarea
              rows={2}
              value={question.text}
              placeholder="What do you want the candidate to answer?"
              onChange={(event) =>
                update(question.key, { text: event.target.value })
              }
            />
          </label>

          <div className="question-row-meta">
            <label>
              Scored as
              <select
                value={question.competency}
                onChange={(event) =>
                  update(question.key, {
                    competency: event.target
                      .value as QuestionDraft["competency"],
                  })
                }
              >
                {COMPETENCY_OPTIONS.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Answer time
              <select
                value={question.time_limit_seconds}
                onChange={(event) =>
                  update(question.key, {
                    time_limit_seconds: Number(event.target.value),
                  })
                }
              >
                {TIME_LIMIT_OPTIONS.map((seconds) => (
                  <option key={seconds} value={seconds}>
                    {formatSeconds(seconds)}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <p className="question-row-note">
            {COMPETENCY_OPTIONS.find(
              (option) => option.id === question.competency,
            )?.hint}
            {" · "}
            {formatSeconds(question.time_limit_seconds)} to answer, after{" "}
            {PREPARATION_SECONDS}s to prepare
          </p>
        </div>
      ))}

      <div className="question-editor-actions">
        <button
          type="button"
          className="button button--secondary"
          onClick={() => onChange([...questions, blankQuestion()])}
        >
          <Icon name="plus" size={13} /> Add question
        </button>

        {questions.length === 0 ? (
          <button
            type="button"
            className="button button--secondary"
            onClick={() => onChange(defaultTemplate())}
          >
            Start from the default set
          </button>
        ) : null}
      </div>

      {questions.length > 0 ? (
        <p className="helper-text">
          <Icon name="clock" size={13} />
          <span>
            {questions.length}{" "}
            {questions.length === 1 ? "question" : "questions"} ·{" "}
            {formatSeconds(candidateTimeSeconds(questions))} of the candidate's
            time, including {PREPARATION_SECONDS}s preparation per question.
          </span>
        </p>
      ) : null}

      {uncovered.length > 0 && questions.length > 0 ? (
        <p className="helper-text">
          <Icon name="info" size={13} />
          <span>
            No question covers{" "}
            {uncovered.map((option) => option.label).join(" or ")}. Those rubric
            competencies will be reported as unscored, and their weight shared
            across the rest.
          </span>
        </p>
      ) : null}
    </fieldset>
  );
}
