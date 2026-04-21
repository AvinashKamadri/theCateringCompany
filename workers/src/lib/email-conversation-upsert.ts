import { randomUUID } from 'crypto';
import prisma from './prisma';
import { embedText } from './openai-embeddings';
import { upsertConversation } from './qdrant-client';
import type { ParsedEmail } from './gmail-parser';
import type { Logger } from 'pino';

interface UpsertArgs {
  clientUserId: string;
  projectId: string;
  clientEmail: string;
  parsed: ParsedEmail;
  log: Logger;
}

export async function upsertEmailConversation({
  clientUserId,
  projectId,
  clientEmail,
  parsed,
  log,
}: UpsertArgs): Promise<void> {
  // Build the new message entry to append
  const entry =
    `[${parsed.date}] From: ${clientEmail}\nSubject: ${parsed.subject}\n\n${parsed.cleanedText}\n\n${'─'.repeat(60)}\n\n`;

  // Find or create the conversation doc for this user+project
  const existing = await prisma.email_conversations.findUnique({
    where: { user_id_project_id: { user_id: clientUserId, project_id: projectId } },
  });

  const fullText = existing ? existing.full_text + entry : entry;
  const messageCount = (existing?.message_count ?? 0) + 1;
  const qdrantPointId = existing?.qdrant_point_id ?? randomUUID();

  // Fetch project details for Qdrant payload
  const project = await prisma.projects.findUnique({
    where: { id: projectId },
    select: { title: true, event_date: true },
  });

  // Upsert DB first
  await prisma.email_conversations.upsert({
    where: { user_id_project_id: { user_id: clientUserId, project_id: projectId } },
    create: {
      user_id: clientUserId,
      project_id: projectId,
      full_text: fullText,
      message_count: messageCount,
      qdrant_point_id: qdrantPointId,
      last_email_at: new Date(parsed.date || Date.now()),
    },
    update: {
      full_text: fullText,
      message_count: messageCount,
      qdrant_point_id: qdrantPointId,
      last_email_at: new Date(parsed.date || Date.now()),
    },
  });

  // Embed full conversation text
  const vector = await embedText(fullText);

  // Upsert Qdrant point (same ID = update existing)
  await upsertConversation(qdrantPointId, vector, {
    user_id: clientUserId,
    project_id: projectId,
    client_email: clientEmail,
    full_text: fullText,
    message_count: messageCount,
    last_email_at: new Date(parsed.date || Date.now()).toISOString(),
    event_title: project?.title ?? 'Email Inquiry',
    event_date: project?.event_date?.toISOString().split('T')[0] ?? null,
  });

  log.info({ clientUserId, projectId, messageCount, qdrantPointId }, 'email_conversation upserted');
}
