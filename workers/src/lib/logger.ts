import pino from 'pino';

const logger = pino({
  level: process.env.LOG_LEVEL || 'info',
  transport: process.env.NODE_ENV === 'development' ? { target: 'pino-pretty' } : undefined,
});

export function createJobLogger(queueName: string, jobId: string, userId?: string, projectId?: string) {
  return logger.child({ queue: queueName, jobId, userId, projectId });
}

export default logger;
