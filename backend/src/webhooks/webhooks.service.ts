import { Inject, Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { createHash } from 'crypto';
import { JobQueueService } from '../job_queue/job-queue.service';
import { PrismaService } from '../prisma.service';
import {
  PAYMENT_PROVIDER,
  PaymentProvider,
} from '../payments/payment-provider.interface';

@Injectable()
export class WebhooksService {
  private readonly logger = new Logger(WebhooksService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly config: ConfigService,
    @Inject(PAYMENT_PROVIDER) private readonly paymentProvider: PaymentProvider,
    private readonly jobQueue: JobQueueService,
  ) {}

  async handleStripeWebhook(rawBody: Buffer, signature: string): Promise<void> {
    const stripeEnabled = this.config.get('STRIPE_ENABLED') === 'true';

    let event: any;
    let eventType: string | undefined;
    let externalEventId: string | undefined;

    if (stripeEnabled) {
      const webhookSecret = this.config.get<string>('STRIPE_WEBHOOK_SECRET')!;
      event = this.paymentProvider.constructWebhookEvent(
        rawBody,
        signature,
        webhookSecret,
      );
      eventType = event.type;
      externalEventId = event.id;
    } else {
      event = JSON.parse(rawBody.toString());
      eventType = event.type;
      externalEventId = event.id;
    }

    const idempotencyHash = createHash('sha256')
      .update(rawBody)
      .digest('hex');

    const webhookEvent = await this.prisma.webhook_events.create({
      data: {
        provider: 'stripe',
        external_event_id: externalEventId || 'unknown',
        event_type: eventType,
        payload: event,
        idempotency_hash: idempotencyHash,
        status: 'pending',
      },
    });

    await this.jobQueue.send('webhooks', {
      webhookEventId: webhookEvent.id,
    });

    this.logger.log(
      `Stripe webhook event ${webhookEvent.id} persisted and enqueued (type: ${eventType})`,
    );
  }

  async handleGenericWebhook(
    provider: string,
    rawBody: Buffer,
  ): Promise<void> {
    let payload: any;
    try {
      payload = JSON.parse(rawBody.toString());
    } catch {
      payload = { raw: rawBody.toString() };
    }

    const externalEventId = payload?.id ?? undefined;

    const idempotencyHash = createHash('sha256')
      .update(rawBody)
      .digest('hex');

    const webhookEvent = await this.prisma.webhook_events.create({
      data: {
        provider,
        external_event_id: externalEventId,
        event_type: payload?.type ?? payload?.event_type,
        payload,
        idempotency_hash: idempotencyHash,
        status: 'pending',
      },
    });

    await this.jobQueue.send('webhooks', {
      webhookEventId: webhookEvent.id,
    });

    this.logger.log(
      `Generic webhook event ${webhookEvent.id} persisted and enqueued (provider: ${provider})`,
    );
  }

  /**
   * Handle DocuSeal webhook — called directly (not via queue) for low-latency status updates.
   * DocuSeal fires submission.completed when all signers have signed.
   */
  async handleDocuSealWebhook(rawBody: Buffer): Promise<void> {
    let payload: any;
    try {
      payload = JSON.parse(rawBody.toString());
    } catch {
      this.logger.warn('DocuSeal webhook: could not parse body');
      return;
    }

    this.logger.log(`DocuSeal webhook received: ${JSON.stringify(payload?.event_type ?? payload?.event)}`);

    const eventType: string = payload?.event_type ?? payload?.event ?? '';

    // submission.completed fires when ALL signers have signed — the only event that should mark the contract signed.
    // form.completed fires per-signer (partial) — log and ignore.
    if (eventType === 'form.completed') {
      this.logger.log(`DocuSeal webhook: ignoring per-signer "form.completed" event (waiting for submission.completed)`);
      return;
    }

    if (eventType !== 'submission.completed') {
      this.logger.log(`DocuSeal webhook: ignoring event type "${eventType}"`);
      return;
    }

    // DocuSeal sends submission id as payload.submission.id or payload.data.id
    const submissionId = String(
      payload?.submission?.id ?? payload?.data?.submission_id ?? payload?.data?.id ?? '',
    );

    if (!submissionId) {
      this.logger.warn('DocuSeal webhook: no submission id found in payload');
      return;
    }

    this.logger.log(`DocuSeal webhook: submission ${submissionId} completed — looking up contract`);

    // Find the contract whose metadata contains this opensign_document_id
    const contracts = await this.prisma.contracts.findMany({
      where: {
        deleted_at: null,
        status: { not: 'signed' },
      },
      select: { id: true, metadata: true, project_id: true },
    });

    const contract = contracts.find((c) => {
      const meta = c.metadata as any;
      return String(meta?.opensign_document_id) === submissionId;
    });

    if (!contract) {
      this.logger.warn(`DocuSeal webhook: no contract found for submission ${submissionId}`);
      return;
    }

    const existingMeta = (contract.metadata as any) ?? {};
    await this.prisma.contracts.update({
      where: { id: contract.id },
      data: {
        status: 'signed',
        metadata: {
          ...existingMeta,
          signed_at: new Date().toISOString(),
          docuseal_completed_event: eventType,
        },
      },
    });

    this.logger.log(`✅ Contract ${contract.id} marked as signed via DocuSeal webhook`);

    // Also advance the parent project to "confirmed" (unless already completed/cancelled)
    if (contract.project_id) {
      const project = await this.prisma.projects.findUnique({
        where: { id: contract.project_id },
        select: { status: true },
      });
      if (project && project.status !== 'completed' && project.status !== 'cancelled') {
        await this.prisma.projects.update({
          where: { id: contract.project_id },
          data: { status: 'confirmed' },
        });
        this.logger.log(`✅ Project ${contract.project_id} advanced to "confirmed" after contract signing`);
      }
    }
  }
}
