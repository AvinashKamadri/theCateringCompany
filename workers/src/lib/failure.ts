import prisma from './prisma';
import logger from './logger';

const MAX_RETRIES = parseInt(process.env.WORKER_MAX_RETRIES || '5', 10);

export async function handleExhaustedRetries(
  queueName: string,
  jobId: string,
  error: string,
  attemptsMade: number,
  entityId?: string,
  userId?: string,
  projectId?: string,
) {
  if (attemptsMade < MAX_RETRIES) return;

  logger.error({ queueName, jobId, error, attemptsMade }, 'Job exhausted all retries, creating manual review event');

  await prisma.events.create({
    data: {
      event_type: 'worker.exhausted_retries',
      project_id: projectId || null,
      actor_id: userId || null,
      payload: { queueName, jobId, error, attemptsMade, entityId },
    },
  });
}
