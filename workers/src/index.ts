// eslint-disable-next-line @typescript-eslint/no-var-requires, @typescript-eslint/no-require-imports
const PgBossModule = require('pg-boss');
const PgBoss = PgBossModule.PgBoss ?? PgBossModule.default ?? PgBossModule;
import 'dotenv/config';
import logger from './lib/logger';
import { processWebhook } from './processors/webhooks.processor';
import { processPayment } from './processors/payments.processor';
import { processPdf } from './processors/pdf.processor';
import { processVector } from './processors/vector.processor';
import { processNotification } from './processors/notifications.processor';
import { processVirusScan } from './processors/virus_scan.processor';
import { processPricing } from './processors/pricing.processor';
import { processGmailSync } from './processors/gmail-sync.processor';
import { processGmailFullSync } from './processors/gmail-full-sync.processor';

const DATABASE_URL = process.env.DATABASE_URL;
if (!DATABASE_URL) {
  logger.error('DATABASE_URL is not set');
  process.exit(1);
}

async function start() {
  const boss = new PgBoss({
    connectionString: DATABASE_URL,
    deleteAfterDays: 1,
    archiveCompletedAfterSeconds: 3600,
    retryLimit: 5,
    retryDelay: 30,
    retryBackoff: true,
  });

  boss.on('error', (err: unknown) => logger.error({ err }, 'pg-boss error'));

  await boss.start();
  logger.info('pg-boss worker started');

  const VECTOR_ENABLED = process.env.VECTOR_ENABLED === 'true';

  // pg-boss v12 requires queues to be created before workers can subscribe
  const GMAIL_ENABLED = process.env.GMAIL_ENABLED === 'true';

  const queues = ['webhooks', 'payments', 'pdf_generation', 'notifications', 'virus_scan', 'pricing_recalc'];
  if (VECTOR_ENABLED) queues.push('vector_indexing');
  if (GMAIL_ENABLED) queues.push('gmail-sync', 'gmail-full-sync');
  for (const q of queues) {
    await boss.createQueue(q).catch(() => { /* already exists */ });
  }

  const wrap = (fn: (job: any) => Promise<void>) => async (jobs: any[]) => {
    await Promise.allSettled(jobs.map(fn));
  };

  await boss.work('webhooks',       { teamSize: 5, teamConcurrency: 2 }, wrap(processWebhook));
  await boss.work('payments',       { teamSize: 3, teamConcurrency: 1 }, wrap(processPayment));
  await boss.work('pdf_generation', { teamSize: 3, teamConcurrency: 1 }, wrap(processPdf));
  await boss.work('notifications',  { teamSize: 5, teamConcurrency: 2 }, wrap(processNotification));
  await boss.work('virus_scan',     { teamSize: 3, teamConcurrency: 1 }, wrap(processVirusScan));
  await boss.work('pricing_recalc', { teamSize: 2, teamConcurrency: 1 }, wrap(processPricing));

  if (VECTOR_ENABLED) {
    await boss.work('vector_indexing', { teamSize: 3, teamConcurrency: 1 }, wrap(processVector));
    logger.info('Vector indexing worker registered');
  }

  if (GMAIL_ENABLED) {
    await boss.work('gmail-sync',      { teamSize: 3, teamConcurrency: 1 }, wrap(processGmailSync));
    await boss.work('gmail-full-sync', { teamSize: 1, teamConcurrency: 1 }, wrap(processGmailFullSync));
    logger.info('Gmail sync workers registered');
  }

  logger.info('All workers registered');

  const shutdown = async (signal: string) => {
    logger.info({ signal }, 'Shutting down workers');
    await boss.stop({ graceful: true, timeout: 10_000 });
    process.exit(0);
  };
  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT',  () => shutdown('SIGINT'));
}

start().catch((err) => {
  logger.error({ err }, 'Failed to start workers');
  process.exit(1);
});
