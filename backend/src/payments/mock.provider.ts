import { Injectable } from '@nestjs/common';
import { PaymentProvider } from './payment-provider.interface';

@Injectable()
export class MockPaymentProvider implements PaymentProvider {
  async createPaymentIntent(
    amount: number,
    currency: string,
    idempotencyKey: string,
    metadata?: Record<string, string>,
  ) {
    return {
      id: `mock_pi_${idempotencyKey}`,
      clientSecret: `mock_secret_${idempotencyKey}`,
    };
  }

  constructWebhookEvent(rawBody: Buffer, signature: string, secret: string) {
    return JSON.parse(rawBody.toString());
  }
}
