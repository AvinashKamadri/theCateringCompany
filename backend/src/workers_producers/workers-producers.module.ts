import { Module } from '@nestjs/common';
import { BullModule } from '@nestjs/bullmq';

export const QUEUE_NAMES = {
  WEBHOOKS: 'webhooks',
  PAYMENTS: 'payments',
  PDF_GENERATION: 'pdf_generation',
  VECTOR_INDEXING: 'vector_indexing',
  NOTIFICATIONS: 'notifications',
  VIRUS_SCAN: 'virus_scan',
  PRICING_RECALC: 'pricing_recalc',
} as const;

@Module({
  imports: [
    BullModule.registerQueue(
      { name: QUEUE_NAMES.WEBHOOKS },
      { name: QUEUE_NAMES.PAYMENTS },
      { name: QUEUE_NAMES.PDF_GENERATION },
      { name: QUEUE_NAMES.VECTOR_INDEXING },
      { name: QUEUE_NAMES.NOTIFICATIONS },
      { name: QUEUE_NAMES.VIRUS_SCAN },
      { name: QUEUE_NAMES.PRICING_RECALC },
    ),
  ],
  exports: [BullModule],
})
export class WorkersProducersModule {}
