import { Controller, ForbiddenException, Post, Body } from '@nestjs/common';
import { PaymentsService } from './payments.service';
import { PaymentRemindersService } from './payment-reminders.service';
import { CurrentUser } from '../common/decorators/current-user.decorator';
import { JwtPayload } from '../common/interfaces/jwt-payload.interface';

@Controller('payments')
export class PaymentsController {
  constructor(
    private readonly paymentsService: PaymentsService,
    private readonly reminders: PaymentRemindersService,
  ) {}

  /** Staff-only manual trigger for the reminder sweep (also runs on daily cron). */
  @Post('reminders/run')
  async runReminders(@CurrentUser() user: JwtPayload) {
    const email = (user as unknown as { email?: string }).email || '';
    if (!email.endsWith('@catering-company.com')) {
      throw new ForbiddenException('Staff only');
    }
    return this.reminders.scanAndNotify();
  }

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
