import { Inject, Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { PrismaService } from '../prisma.service';
import {
  PAYMENT_PROVIDER,
  PaymentProvider,
} from './payment-provider.interface';

@Injectable()
export class PaymentsService {
  private readonly logger = new Logger(PaymentsService.name);

  constructor(
    @Inject(PAYMENT_PROVIDER) private readonly paymentProvider: PaymentProvider,
    private readonly prisma: PrismaService,
    private readonly config: ConfigService,
  ) {}

  async createPaymentIntent(
    clientId: string,
    projectId: string,
    amount: number,
    currency: string,
    idempotencyKey: string,
  ): Promise<{ clientSecret: string; paymentRequestId: string }> {
    const stripeEnabled = this.config.get('STRIPE_ENABLED') === 'true';

    // Always create payment_requests row first
    const paymentRequest = await this.prisma.payment_requests.create({
      data: {
        client_id: clientId,
        idempotency_key: idempotencyKey,
        status: 'pending',
      },
    });

    if (!stripeEnabled) {
      // Mock mode: create payment directly with mock id
      const mockId = `mock_pi_${idempotencyKey}`;

      await this.prisma.payments.create({
        data: {
          project_id: projectId,
          payment_request_id: paymentRequest.id,
          gateway_payment_intent_id: mockId,
          amount,
          currency,
          status: 'pending',
          idempotency_key: idempotencyKey,
        },
      });

      this.logger.log(
        `Mock payment intent created for request ${paymentRequest.id}`,
      );

      return {
        clientSecret: `mock_secret_${idempotencyKey}`,
        paymentRequestId: paymentRequest.id,
      };
    }

    // Stripe enabled: call real provider
    const { id, clientSecret } =
      await this.paymentProvider.createPaymentIntent(
        amount,
        currency,
        idempotencyKey,
        {
          projectId,
          paymentRequestId: paymentRequest.id,
        },
      );

    await this.prisma.payments.create({
      data: {
        project_id: projectId,
        payment_request_id: paymentRequest.id,
        gateway_payment_intent_id: id,
        amount,
        currency,
        status: 'pending',
        idempotency_key: idempotencyKey,
      },
    });

    this.logger.log(
      `Stripe payment intent ${id} created for request ${paymentRequest.id}`,
    );

    return { clientSecret, paymentRequestId: paymentRequest.id };
  }
}
