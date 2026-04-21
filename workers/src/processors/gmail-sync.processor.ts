import prisma from '../lib/prisma';
import { createJobLogger } from '../lib/logger';
import { getValidAccessToken, fetchHistoryMessageIds, fetchMessage } from '../lib/gmail-client';
import { parseMessage, extractEmail, isAutomatedEmail } from '../lib/gmail-parser';
import { resolveClientIdentity, resolveClientProject, resolveProjectFromThread, autoCreateProject } from '../lib/identity-resolver';
import { ensureCollection } from '../lib/qdrant-client';
import { upsertEmailConversation } from '../lib/email-conversation-upsert';
import type { GmailSyncJobData } from '../types/jobs';

export async function processGmailSync(job: { id: string; data: GmailSyncJobData }): Promise<void> {
  const { userId, historyId, webhookEventId } = job.data;
  const log = createJobLogger('gmail-sync', job.id, userId ?? '');

  log.info({ userId, historyId }, 'Starting incremental Gmail sync');

  if (!userId) {
    log.warn('No userId in job data — aborting');
    return;
  }

  // ── Step 2a: Get valid access token ─────────────────────────────────────────
  let accessToken: string;
  try {
    accessToken = await getValidAccessToken(userId);
  } catch (err: any) {
    log.warn({ userId, err: err.message }, 'Cannot get access token — aborting sync');
    return;
  }

  // ── Step 2b: Fetch new message IDs via Gmail history API ────────────────────
  const syncState = await prisma.gmail_sync_state.findUnique({ where: { user_id: userId } });
  const startHistoryId = historyId ?? syncState?.history_id;

  if (!startHistoryId) {
    log.info({ userId }, 'No historyId available — enqueue gmail-full-sync instead');
    return;
  }

  let historyResult;
  try {
    historyResult = await fetchHistoryMessageIds(accessToken, startHistoryId);
  } catch (err: any) {
    log.error({ err: err.message }, 'Failed to fetch Gmail history');
    throw err;
  }

  const { messageIds, newHistoryId } = historyResult;
  log.info({ count: messageIds.length, newHistoryId }, 'New messages found');

  if (messageIds.length === 0) {
    await prisma.gmail_sync_state.update({
      where: { user_id: userId },
      data: { history_id: newHistoryId, last_synced: new Date() },
    });
    return;
  }

  const companyEmailSet = await loadCompanyEmailSet();
  await ensureCollection();

  // ── Step 2c: Fetch + parse each message ─────────────────────────────────────
  let processed = 0;

  for (const { id: messageId } of messageIds) {
    try {
      const rawMessage = await fetchMessage(accessToken, messageId);
      const parsed = parseMessage(rawMessage);

      log.info(
        { messageId, from: parsed.from, subject: parsed.subject, chars: parsed.cleanedText.length },
        'Message fetched and parsed',
      );

      if (parsed.cleanedText.length < 20) {
        log.info({ messageId }, 'Skipping — cleaned text too short');
        continue;
      }

      // ── Step 2.5: Skip automated / bot emails ────────────────────────────────
      if (isAutomatedEmail(rawMessage)) {
        log.info({ messageId, from: parsed.from }, 'Skipping automated/bot email');
        continue;
      }

      const clientEmail = extractEmail(parsed.from);

      // ── Step 3: Strip company-side messages ──────────────────────────────────
      if (companyEmailSet.has(clientEmail)) {
        log.info({ messageId, clientEmail }, 'Skipping company-side message');
        continue;
      }

      // ── Step 4: Resolve client identity ──────────────────────────────────────
      const { userId: clientUserId, identityConfidence } = await resolveClientIdentity(
        clientEmail,
        parsed.threadId,
      );

      log.info({ messageId, clientEmail, clientUserId, identityConfidence }, 'Client identity resolved');

      // ── Step 5: Resolve project ──────────────────────────────────────────────────
      // Layer 1: thread already has a project assignment
      let projectId: string | null = await resolveProjectFromThread(parsed.threadId);

      if (!projectId) {
        const emailHint = `${parsed.subject}\n${parsed.cleanedText.slice(0, 300)}`;
        const resolution = await resolveClientProject(clientUserId, clientEmail, emailHint);

        if (resolution.status === 'resolved') {
          projectId = resolution.projectId;
        } else if (resolution.status === 'none') {
          projectId = await autoCreateProject(clientUserId);
        } else {
          log.warn({ messageId, clientEmail }, 'Ambiguous project — skipping embed');
          continue;
        }
      }

      // Minimal record for thread→project tracking on future replies
      await prisma.email_chunks.upsert({
        where: { gmail_message_id_chunk_index: { gmail_message_id: messageId, chunk_index: 0 } },
        create: {
          gmail_message_id: messageId,
          gmail_thread_id: parsed.threadId,
          user_id: clientUserId,
          project_id: projectId,
          chunk_index: 0,
          chunk_text: parsed.cleanedText,
          client_email: clientEmail,
          identity_status: 'resolved',
        },
        update: {
          user_id: clientUserId,
          project_id: projectId,
          chunk_text: parsed.cleanedText,
          identity_status: 'resolved',
        },
      });

      // ── Steps 6 & 7: Accumulate conversation + embed + upsert Qdrant ──────────
      await upsertEmailConversation({
        clientUserId,
        projectId,
        clientEmail,
        parsed,
        log,
      });

      processed++;
    } catch (err: any) {
      log.error({ messageId, err: err.message }, 'Error processing message — skipping');
    }
  }

  // ── Update sync state ────────────────────────────────────────────────────────
  await prisma.gmail_sync_state.update({
    where: { user_id: userId },
    data: { history_id: newHistoryId, last_synced: new Date() },
  });

  if (webhookEventId) {
    await prisma.webhook_events.update({
      where: { id: webhookEventId },
      data: { status: 'processed', processed_at: new Date() },
    }).catch(() => { /* non-critical */ });
  }

  log.info({ processed, total: messageIds.length, newHistoryId }, 'Gmail sync complete');
}

// ── Helpers ───────────────────────────────────────────────────────────────────

async function loadCompanyEmailSet(): Promise<Set<string>> {
  const rows = await prisma.company_emails.findMany({ select: { email: true } });
  return new Set(rows.map((r) => r.email));
}
