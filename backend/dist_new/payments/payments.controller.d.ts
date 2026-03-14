import { PaymentsService } from './payments.service';
import { JwtPayload } from '../common/interfaces/jwt-payload.interface';
export declare class PaymentsController {
    private readonly paymentsService;
    constructor(paymentsService: PaymentsService);
    createPaymentIntent(user: JwtPayload, body: {
        amount: number;
        currency: string;
        projectId: string;
        idempotencyKey: string;
    }): Promise<{
        clientSecret: string;
        paymentRequestId: string;
    }>;
}
