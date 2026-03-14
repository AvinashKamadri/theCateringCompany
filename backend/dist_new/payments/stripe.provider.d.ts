import { ConfigService } from '@nestjs/config';
import Stripe from 'stripe';
import { PaymentProvider } from './payment-provider.interface';
export declare class StripeProvider implements PaymentProvider {
    private config;
    private stripe;
    constructor(config: ConfigService);
    createPaymentIntent(amount: number, currency: string, idempotencyKey: string, metadata?: Record<string, string>): Promise<{
        id: string;
        clientSecret: string;
    }>;
    constructWebhookEvent(rawBody: Buffer, signature: string, secret: string): Stripe.Event;
}
