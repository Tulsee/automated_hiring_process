/**
 * Plain-language explanations of the backend's quality flags.
 *
 * Each is written for a recruiter: what happened, and what it means for the
 * score they are looking at.
 */

import { humanise } from "./format";

const FLAG_COPY: Record<string, string> = {
  empty_answer: "No speech was recorded, so this question was not scored.",
  empty_transcript: "No speech was detected in the recording.",
  answer_too_short:
    "Too short to judge fairly, so this question was not scored.",
  transcript_too_short: "The answer was very short.",
  off_topic: "The answer did not address the question asked.",
  unverified_quote:
    "The supporting quote could not be found in the transcript, so treat this score with caution.",
  no_evidence_quote: "No supporting quote was given for this score.",
  scoring_failed: "Scoring did not complete for this answer.",
  low_confidence:
    "Speech-to-text was unsure here; check the audio before relying on it.",
  unanswered_question: "The candidate did not answer this question.",
  not_transcribed: "This answer has not been transcribed yet.",
  no_scores: "Nothing could be scored for this interview.",
};

export function flagLabel(flag: string): string {
  return FLAG_COPY[flag] ?? humanise(flag);
}
