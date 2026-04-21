import prisma from '../lib/prisma';
import { createJobLogger } from '../lib/logger';
import { getValidAccessToken, listAllMessageIds, fetchMessage } from '../lib/gmail-client';
import { parseMessage, extractEmail, isAutomatedEmail } from '../lib/gmail-parser';
import { resolveClientIdentity, resolveClientProject, resolveProjectFromThread, autoCreateProject } from '../lib/identity-resolver';
import { ensureCollection } from '../lib/qdrant-client';
import { upsertEmailConversation } from '../lib/email-conversation-upsert';
import type { GmailFullSyncJobData } from '../types/jobs';

const BATCH_SIZE = 20;

export async function processGmailFullSync(job: { id: string; data: GmailFullSyncJobData }): Promise<void> {
  const { userId } = job.data;
  const log = createJobLogger('gmail-full-sync', job.id, userId);

  log.info({ userId }, 'Starting full Gmail sync');

  if (!userId) {
    log.warn('No userId in job data — aborting');
    return;
  }

  // ── Step 2a: Get valid access token ─────────────────────────────────────────
  let accessToken: string;
  try {
    accessToken = await getValidAccessToken(userId);
  } catch (err: any) {
    log.warn({ userId, err: err.message }, 'Cannot get access token — aborting full sync');
    return;
  }

  const companyEmailSet = await loadCompanyEmailSet();
  await ensureCollection();

  let pageToken: string | undefined;
  let totalProcessed = 0;
  let totalSkipped = 0;
  let finalHistoryId: string | undefined;

  // Resume from saved pageToken if this job was previously interrupted
  const syncState = await prisma.gmail_sync_state.findUnique({ where: { user_id: userId } });
  if (syncState?.history_id && syncState.history_id.startsWith('page:')) {
    pageToken = syncState.history_id.replace('page:', '');
    log.info({ pageToken }, 'Resuming full sync from saved page token');
  }

  // ── Paginate through all inbox messages ──────────────────────────────────────
  do {
    let listResult;
    try {
      listResult = await listAllMessageIds(accessToken, pageToken);
    } catch (err: any) {
      log.error({ err: err.message }, 'Failed to list messages');
      throw err;
    }

    finalHistoryId = listResult.historyId ?? finalHistoryId;
    pageToken = listResult.nextPageToken;

    log.info(
      { batchSize: listResult.messageIds.length, hasMore: !!pageToken },
      'Processing message batch',
    );

    if (pageToken) {
      await prisma.gmail_sync_state.update({
        where: { user_id: userId },
        data: { history_id: `page:${pageToken}` },
      });
    }

    // ── Steps 2b–5: Fetch, parse, filter, identify, accumulate ──────────────
    const batches = chunk(listResult.messageIds, BATCH_SIZE);
    for (const batch of batches) {
      await Promise.allSettled(
        batch.map(async ({ id: messageId }) => {
          try {
            const rawMessage = await fetchMessage(accessToken, messageId);
            const parsed = parseMessage(rawMessage);

            if (parsed.cleanedText.length < 20) {
              totalSkipped++;
              return;
            }

            if (isAutomatedEmail(rawMessage)) {
              totalSkipped++;
              return;
            }

            const clientEmail = extractEmail(parsed.from);

            if (companyEmailSet.has(clientEmail)) {
              totalSkipped++;
              return;
            }

            // ── Step 4: Resolve client identity ──────────────────────────────
            const { userId: clientUserId, identityConfidence } = await resolveClientIdentity(
              clientEmail,
              parsed.threadId,
            );

            log.debug({ messageId, clientEmail, clientUserId, identityConfidence }, 'Identity resolved');

            // ── Step 5: Resolve project ──────────────────────────────────────
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
                totalSkipped++;
                return;
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

            // ── Steps 6 & 7: Accumulate conversation + embed + upsert Qdrant ──
            await upsertEmailConversation({
              clientUserId,
              projectId,
              clientEmail,
              parsed,
              log,
            });

            totalProcessed++;
          } catch (err: any) {
            log.error({ messageId, err: err.message }, 'Error processing message');
          }
        }),
      );
    }
  } while (pageToken);

  // ── Finalize: save real historyId ────────────────────────────────────────────
  await prisma.gmail_sync_state.update({
    where: { user_id: userId },
    data: { history_id: finalHistoryId ?? null, last_synced: new Date() },
  });

  log.info({ totalProcessed, totalSkipped, finalHistoryId }, 'Full Gmail sync complete');
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function chunk<T>(arr: T[], size: number): T[][] {
  const out: T[][] = [];
  for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size));
  return out;
}

async function loadCompanyEmailSet(): Promise<Set<string>> {
  const rows = await prisma.company_emails.findMany({ select: { email: true } });
  return new Set(rows.map((r) => r.email));
}
