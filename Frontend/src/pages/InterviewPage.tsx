/**
 * The candidate's recorded interview.
 *
 * Each question runs the same three steps:
 *
 *   1. **Prepare** — 30 seconds with the question on screen and nothing being
 *      recorded, so the candidate can think. They may start early.
 *   2. **Record** — recording begins *automatically* when preparation ends, and
 *      stops automatically at the question's own time limit.
 *   3. **Upload** — the answer is sent, then the next question's preparation
 *      begins.
 *
 * Why automatic: a candidate who must press record at the moment the clock
 * starts is penalised for hesitating. Announcing the transition and starting it
 * for them makes the timing identical for everyone — the same reason the
 * questions and the rubric are fixed rather than improvised.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { useApi } from "../hooks/useApi";
import { useCountdown, useMediaRecorder } from "../hooks/useMediaRecorder";
import { Icon } from "../components/Icon";
import {
  ErrorState,
  Loading,
  Notice,
  Panel,
  ProgressBar,
} from "../components/primitives";
import { formatSeconds, humanise } from "../lib/format";
import type { InterviewQuestion, InterviewSession } from "../types";

/** Thinking time before recording starts, for every question. */
export const PREPARATION_SECONDS = 30;

type Phase =
  | "intro"
  | "camera"
  | "preparing"
  | "recording"
  | "uploading"
  | "submitted"
  | "failed";

/**
 * Loads the invite, then hands the session to the flow below.
 *
 * Split in two deliberately: the flow initialises its state *from props*, so
 * nothing has to be copied out of the fetched session by an effect.
 */
export function InterviewPage({ token }: { token: string }) {
  const invite = useApi(() => api.getInvite(token), [token]);

  if (invite.loading) {
    return (
      <div className="candidate-portal">
        <Panel>
          <Loading what="your interview" />
        </Panel>
      </div>
    );
  }

  if (invite.error || !invite.data) {
    return (
      <div className="candidate-portal">
        <Panel title="This link does not work">
          {invite.error ? <ErrorState error={invite.error} /> : null}
          <p className="muted">
            Invite links expire. If yours has, ask the hiring team for a new
            one.
          </p>
        </Panel>
      </div>
    );
  }

  return (
    <InterviewFlow key={invite.data.id} token={token} session={invite.data} />
  );
}

function InterviewFlow({
  token,
  session,
}: {
  token: string;
  session: InterviewSession;
}) {
  // The starting phase is read from the session: an already-submitted
  // interview is finished, and an acknowledged one resumes at the camera step.
  const [phase, setPhase] = useState<Phase>(() => {
    if (session.status === "submitted") return "submitted";
    if (session.intro_acknowledged && session.question) return "camera";
    return "intro";
  });

  const [question, setQuestion] = useState<InterviewQuestion | null>(
    session.question,
  );
  const [sessionId, setSessionId] = useState(session.id);
  const [answered, setAnswered] = useState(session.current_question_index);
  const [total, setTotal] = useState(session.total_questions);
  const [failure, setFailure] = useState<string | null>(null);

  const recorder = useMediaRecorder();
  const previewRef = useRef<HTMLVideoElement>(null);

  // Attach the live stream to whichever preview element is mounted.
  useEffect(() => {
    if (previewRef.current && recorder.stream) {
      previewRef.current.srcObject = recorder.stream;
    }
  }, [recorder.stream, phase]);

  /** Stop recording, upload, then move on. */
  const finishAnswer = useCallback(async () => {
    if (!question) return;

    setPhase("uploading");

    const video = await recorder.stop();

    if (!video || video.size === 0) {
      setFailure(
        "Nothing was captured for that answer. Check your camera and microphone, then reload to continue.",
      );
      setPhase("failed");

      return;
    }

    try {
      const result = await api.uploadAnswer(sessionId, question.id, video);

      setAnswered(result.answered_count);
      setTotal(result.total_questions);

      if (result.session_status === "submitted" || !result.next_question) {
        recorder.release();
        setPhase("submitted");

        return;
      }

      // Straight back to preparation for the next question.
      setQuestion(result.next_question);
      setPhase("preparing");
    } catch (caught: unknown) {
      setFailure(
        caught instanceof Error ? caught.message : "The upload failed.",
      );
      setPhase("failed");
    }
  }, [question, recorder, sessionId]);

  /** Preparation is over: start recording without asking. */
  const beginRecording = useCallback(() => {
    if (recorder.start()) {
      setPhase("recording");
    } else {
      setFailure(recorder.error?.message ?? "Recording could not be started.");
      setPhase("failed");
    }
  }, [recorder]);

  const preparationLeft = useCountdown(
    phase === "preparing" ? PREPARATION_SECONDS : null,
    beginRecording,
  );

  const recordingLeft = useCountdown(
    phase === "recording" && question ? question.time_limit_seconds : null,
    finishAnswer,
  );

  return (
    <div className="candidate-portal">
      {phase === "intro" ? (
        <IntroStep
          token={token}
          totalQuestions={session.total_questions}
          totalSeconds={session.total_time_seconds}
          questions={session.questions}
          onStarted={(next, id, count) => {
            setSessionId(id);
            setTotal(count);
            setQuestion(next);
            setPhase("camera");
          }}
        />
      ) : null}

      {phase === "camera" ? (
        <Panel title="Turn on your camera" subtitle="Nothing is recorded yet.">
          <video
            ref={previewRef}
            autoPlay
            muted
            playsInline
            className="interview-preview"
          />

          {recorder.cameraState === "denied" ? (
            <Notice icon="alert" title="No camera access">
              {recorder.error?.message ?? "Your browser blocked the camera."}{" "}
              Allow access in the address bar, then try again.
            </Notice>
          ) : (
            <p className="muted">
              You will see yourself here. Each question gives you{" "}
              {PREPARATION_SECONDS} seconds to think, then recording starts on
              its own.
            </p>
          )}

          <button
            type="button"
            className="button button--primary button--wide"
            disabled={recorder.cameraState === "requesting"}
            onClick={async () => {
              if (await recorder.requestCamera()) setPhase("preparing");
            }}
          >
            {recorder.cameraState === "requesting"
              ? "Waiting for permission…"
              : recorder.cameraState === "denied"
                ? "Try again"
                : "Turn on camera and begin"}
          </button>
        </Panel>
      ) : null}

      {phase === "preparing" ||
      phase === "recording" ||
      phase === "uploading" ? (
        <QuestionStage
          question={question}
          answered={answered}
          total={total}
          phase={phase}
          preparationLeft={preparationLeft}
          recordingLeft={recordingLeft}
          previewRef={previewRef}
          onStartEarly={beginRecording}
          onStopEarly={finishAnswer}
        />
      ) : null}

      {phase === "submitted" ? (
        <Panel title="Interview submitted">
          <p>
            Thank you — all {total || session.total_questions} answers are in. A
            recruiter reviews every interview before any decision is made, and
            you will hear from the team by email.
          </p>
          <p className="candidate-footnote">
            Your answers are transcribed and scored against a written rubric.
            Every score records the words it was based on, and you can ask how
            any score about you was reached.
          </p>
        </Panel>
      ) : null}

      {phase === "failed" ? (
        <Panel title="Something went wrong">
          <Notice icon="alert" title="Your answer was not saved">
            {failure}
          </Notice>
          <button
            type="button"
            className="button button--secondary"
            onClick={() => window.location.reload()}
          >
            Reload and continue
          </button>
        </Panel>
      ) : null}
    </div>
  );
}

/** What the candidate reads before anything is recorded. */
function IntroStep({
  token,
  totalQuestions,
  totalSeconds,
  questions,
  onStarted,
}: {
  token: string;
  totalQuestions: number;
  totalSeconds: number;
  questions: InterviewQuestion[];
  onStarted: (
    question: InterviewQuestion | null,
    sessionId: string,
    total: number,
  ) => void;
}) {
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <>
      <section className="candidate-hero">
        <p className="eyebrow">YOUR INTERVIEW</p>
        <h2>
          {totalQuestions} questions, <span>recorded in your own words</span>
        </h2>
        <p>
          Answer each question on camera. Nothing is recorded until you have had
          time to think.
        </p>
      </section>

      <Panel title="How this works">
        <ul className="interview-rules">
          <li>
            <strong>{PREPARATION_SECONDS} seconds to prepare</strong> before
            every question. The question is on screen and nothing is recording.
          </li>
          <li>
            <strong>Recording starts automatically</strong> when that time is
            up, so everyone gets the same thinking time. You can start sooner if
            you are ready.
          </li>
          <li>
            <strong>Each question has its own limit</strong>, shown while you
            answer. Recording stops by itself when it runs out.
          </li>
          <li>
            <strong>One take per question.</strong> Answers cannot be
            re-recorded, so there is no advantage in rushing.
          </li>
          <li>
            About {formatSeconds(totalSeconds)} of answering time in total, plus
            preparation.
          </li>
        </ul>

        {questions.length > 0 ? (
          <>
            <h3>What you will be asked about</h3>
            <ul
              className="skill-list"
              style={{ listStyle: "none", padding: 0 }}
            >
              {questions.map((entry) => (
                <li key={entry.id} className="skill-chip">
                  {humanise(entry.competency)} ·{" "}
                  {formatSeconds(entry.time_limit_seconds)}
                </li>
              ))}
            </ul>
          </>
        ) : null}

        {error ? (
          <Notice icon="alert" title="Could not start">
            {error}
          </Notice>
        ) : null}

        <button
          type="button"
          className="button button--primary button--wide"
          disabled={starting}
          onClick={async () => {
            setStarting(true);
            setError(null);

            try {
              const started = await api.acknowledgeIntro(token);

              onStarted(
                started.question,
                started.session_id,
                started.total_questions,
              );
            } catch (caught: unknown) {
              setError(
                caught instanceof Error
                  ? caught.message
                  : "Could not start the interview.",
              );
              setStarting(false);
            }
          }}
        >
          {starting ? "Starting…" : "I understand — begin"}
        </button>
      </Panel>
    </>
  );
}

/** The question, the camera, and whichever clock is running. */
function QuestionStage({
  question,
  answered,
  total,
  phase,
  preparationLeft,
  recordingLeft,
  previewRef,
  onStartEarly,
  onStopEarly,
}: {
  question: InterviewQuestion | null;
  answered: number;
  total: number;
  phase: Phase;
  preparationLeft: number | null;
  recordingLeft: number | null;
  previewRef: React.RefObject<HTMLVideoElement | null>;
  onStartEarly: () => void;
  onStopEarly: () => void;
}) {
  if (!question) return null;

  const preparing = phase === "preparing";
  const recording = phase === "recording";

  return (
    <Panel
      title={`Question ${Math.min(answered + 1, total || 1)} of ${total || 1}`}
      subtitle={humanise(question.competency)}
    >
      <ProgressBar
        value={answered}
        max={Math.max(1, total)}
        tone="violet"
        label={`${answered} of ${total} questions answered`}
      />

      <p className="interview-question">{question.text}</p>

      <div className={`interview-stage${recording ? " is-recording" : ""}`}>
        <video
          ref={previewRef}
          autoPlay
          muted
          playsInline
          className="interview-preview"
        />

        {recording ? (
          <p className="recording-badge">
            <span className="recording-dot" aria-hidden="true" />
            Recording
          </p>
        ) : null}
      </div>

      {/* One live region for both clocks, so a screen reader hears the phase
          change and the time left without the page shifting underneath. */}
      <p className="interview-clock" role="status" aria-live="polite">
        {preparing ? (
          <>
            <Icon name="clock" size={15} />
            <strong>{formatSeconds(preparationLeft)}</strong> to prepare —
            recording starts automatically
          </>
        ) : recording ? (
          <>
            <Icon name="mic" size={15} />
            <strong>{formatSeconds(recordingLeft)}</strong> left to answer
          </>
        ) : (
          <>
            <Icon name="upload" size={15} />
            Uploading your answer…
          </>
        )}
      </p>

      {preparing ? (
        <>
          <p className="muted">
            Read the question and plan your answer. You have{" "}
            {formatSeconds(preparationLeft)} left, or start now if you are
            ready.
          </p>
          <button
            type="button"
            className="button button--primary"
            onClick={onStartEarly}
          >
            I am ready — start recording
          </button>
        </>
      ) : null}

      {recording ? (
        <button
          type="button"
          className="button button--secondary"
          onClick={onStopEarly}
        >
          Finish this answer
        </button>
      ) : null}
    </Panel>
  );
}
