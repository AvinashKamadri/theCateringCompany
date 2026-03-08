import { Controller, Post, Body } from '@nestjs/common';
import { PaymentsService } from './payments.service';
import { CurrentUser } from '../common/decorators/current-user.decorator';
import { JwtPayload } from '../common/interfaces/jwt-payload.interface';

@Controller('payments')
export class PaymentsController {
  constructor(private readonly paymentsService: PaymentsService) {}

  @Post('create-intent')
  async createPaymentIntent(
    @CurrentUser() user: JwtPayload,
    @Body()
    body: {
      amount: number;
      currency: string;
      projectId: string;
      idempotencyKey: string;
    },
  ) {
    const { clientSecret, paymentRequestId } =
      await this.paymentsService.createPaymentIntent(
        user.sub,
        body.projectId,
        body.amount,
        body.currency,
        body.idempotencyKey,
      );

    return { clientSecret, paymentRequestId };
  }
}
