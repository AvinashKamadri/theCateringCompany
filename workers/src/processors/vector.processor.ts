

import prisma from '../lib/prisma';
import { createJobLogger } from '../lib/logger';
import type { VectorJobData } from '../types/jobs';
import { randomUUID } from 'crypto';

const VECTOR_ENABLED = process.env.VECTOR_ENABLED === 'true';

export async function processVector(job: { id: string; data: VectorJobData }): Promise<void> {
  const { messageId, content, userId, projectId } = job.data;
  const log = createJobLogger('vector', job.id!, userId, projectId);

  log.info({ messageId }, 'Processing vector indexing');

  // Check if vector indexing is enabled
  if (!VECTOR_ENABLED) {
    log.info('VECTOR_ENABLED=false, skipping vector indexing');
    return;
  }

  const message = await prisma.messages.findUnique({
    where: { id: messageId },
  });

  if (!message) {
    log.warn({ messageId }, 'Message not found, skipping');
    return;
  }

  // Idempotency check
  if (message.vector_status === 'indexed') {
    log.info({ messageId }, 'Message already indexed, skipping');
    return;
  }

  log.info({ messageId, contentLength: content.length }, 'Generating embedding for message');

  // TODO: Call embedding API (e.g., OpenAI embeddings, Cohere, etc.)
  // const embedding = await openai.embeddings.create({
  //   model: 'text-embedding-3-small',
  //   input: content,
  // });

  // TODO: Store embedding in Qdrant
  // const qdrantClient = new QdrantClient({ url: process.env.QDRANT_URL });
  // await qdrantClient.upsert('messages', {
  //   points: [{ id: vectorId, vector: embedding.data[0].embedding, payload: { messageId, projectId } }],
  // });

  // Mock: generate a fake vector ID
  const vectorId = randomUUID();

  log.info({ messageId, vectorId }, 'Embedding generated (mocked), updating message record');

  // Update message with vector information
  await prisma.messages.update({
    where: { id: messageId },
    data: {
      qdrant_vector_id: vectorId,
      vector_status: 'indexed',
      vector_indexed_at: new Date(),
    },
  });

  log.info({ messageId, vectorId }, 'Vector indexing completed');
}
