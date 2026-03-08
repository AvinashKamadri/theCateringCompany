export const PAYMENT_PROVIDER = 'PAYMENT_PROVIDER';

export interface PaymentProvider {
  createPaymentIntent(
    amount: number,
    currency: string,
    idempotencyKey: string,
    metadata?: Record<string, string>,
  ): Promise<{ id: string; clientSecret: string }>;

  constructWebhookEvent(
    rawBody: Buffer,
    signature: string,
    secret: string,
  ): any;
}
