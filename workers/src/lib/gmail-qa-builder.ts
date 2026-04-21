import type { GmailMessage } from './gmail-client';
import { parseMessage, extractEmail, isAutomatedEmail } from './gmail-parser';

export interface QAResult {
  question: string | null; // last company message before this one (null if client emailed first)
  answer: string;          // this client message
  chunkText: string;       // combined text for embedding
}

/**
 * Finds the Q&A pair for a specific client message within a thread.
 * Walks backwards from the target message to find the last company message (Question).
 * Returns null only if the target message is not found in the thread.
 */
export function extractQAForMessage(
  threadMessages: GmailMessage[],
  targetMessageId: string,
  companyEmailSet: Set<string>,
): QAResult | null {
  const targetIndex = threadMessages.findIndex((m) => m.id === targetMessageId);
  if (targetIndex === -1) return null;

  const parsed = parseMessage(threadMessages[targetIndex]);
  const answer = parsed.cleanedText;

  // Walk backwards to find the last company message before this one
  let question: string | null = null;
  for (let i = targetIndex - 1; i >= 0; i--) {
    const msg = threadMessages[i];
    if (isAutomatedEmail(msg)) continue;
    const p = parseMessage(msg);
    const fromEmail = extractEmail(p.from);
    if (companyEmailSet.has(fromEmail)) {
      question = p.cleanedText;
      break;
    }
  }

  const chunkText = question ? `Q: ${question}\n\nA: ${answer}` : answer;

  return { question, answer, chunkText };
}
