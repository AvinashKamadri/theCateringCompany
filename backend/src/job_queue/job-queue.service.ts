import { Injectable, OnModuleInit, OnModuleDestroy, Logger } from '@nestjs/common';

// pg-boss CJS compat — the class is exported as a named export `PgBoss`.
// eslint-disable-next-line @typescript-eslint/no-var-requires, @typescript-eslint/no-require-imports
const PgBossModule = require('pg-boss');
const PgBoss = PgBossModule.PgBoss ?? PgBossModule.default ?? PgBossModule;

@Injectable()
export class JobQueueService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(JobQueueService.name);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private boss: any;

  constructor() {
    this.boss = new PgBoss({
      connectionString: process.env.DATABASE_URL!,
      deleteAfterDays: 1,
      archiveCompletedAfterSeconds: 3600,
      retryLimit: 5,
      retryDelay: 30,
      retryBackoff: true,
    });

    this.boss.on('error', (err: unknown) =>
      this.logger.error('pg-boss error', err),
    );
  }

  async onModuleInit() {
    await this.boss.start();
    this.logger.log('pg-boss started');
  }

  async onModuleDestroy() {
    await this.boss.stop();
    this.logger.log('pg-boss stopped');
  }

  /** Enqueue a job. Returns the job id string or null. */
  async send<T extends object>(queue: string, data: T, options?: Record<string, unknown>): Promise<string | null> {
    return this.boss.send(queue, data, options ?? {});
  }
}
