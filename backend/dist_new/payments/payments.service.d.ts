import { ConfigService } from '@nestjs/config';
import { PrismaService } from '../prisma.service';
import { PaymentProvider } from './payment-provider.interface';
export declare class PaymentsService {
    private readonly paymentProvider;
    private readonly prisma;
    private readonly config;
    private readonly logger;
    constructor(paymentProvider: PaymentProvider, prisma: PrismaService, config: ConfigService);
    createPaymentIntent(clientId: string, projectId: string, amount: number, currency: string, idempotencyKey: string): Promise<{
        clientSecret: string;
        paymentRequestId: string;
    }>;
}
