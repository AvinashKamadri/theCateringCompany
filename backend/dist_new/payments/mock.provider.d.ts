import { PaymentProvider } from './payment-provider.interface';
export declare class MockPaymentProvider implements PaymentProvider {
    createPaymentIntent(amount: number, currency: string, idempotencyKey: string, metadata?: Record<string, string>): Promise<{
        id: string;
        clientSecret: string;
    }>;
    constructWebhookEvent(rawBody: Buffer, signature: string, secret: string): any;
}
