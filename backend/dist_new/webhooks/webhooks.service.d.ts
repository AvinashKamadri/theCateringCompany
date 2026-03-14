import { ConfigService } from '@nestjs/config';
import { Queue } from 'bullmq';
import { PrismaService } from '../prisma.service';
import { PaymentProvider } from '../payments/payment-provider.interface';
export declare class WebhooksService {
    private readonly prisma;
    private readonly config;
    private readonly paymentProvider;
    private readonly webhooksQueue;
    private readonly logger;
    constructor(prisma: PrismaService, config: ConfigService, paymentProvider: PaymentProvider, webhooksQueue: Queue);
    handleStripeWebhook(rawBody: Buffer, signature: string): Promise<void>;
    handleGenericWebhook(provider: string, rawBody: Buffer): Promise<void>;
}
