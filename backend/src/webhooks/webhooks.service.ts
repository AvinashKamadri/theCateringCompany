import { Inject, Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { InjectQueue } from '@nestjs/bullmq';
import { Queue } from 'bullmq';
import { createHash } from 'crypto';
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
    @InjectQueue('webhooks') private readonly webhooksQueue: Queue,
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

    await this.webhooksQueue.add('webhooks', {
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

    await this.webhooksQueue.add('webhooks', {
      webhookEventId: webhookEvent.id,
    });

    this.logger.log(
      `Generic webhook event ${webhookEvent.id} persisted and enqueued (provider: ${provider})`,
    );
  }
}
