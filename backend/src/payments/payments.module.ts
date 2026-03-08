import { Module } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { PaymentsController } from './payments.controller';
import { PaymentsService } from './payments.service';
import { PAYMENT_PROVIDER } from './payment-provider.interface';
import { StripeProvider } from './stripe.provider';
import { MockPaymentProvider } from './mock.provider';
import { PrismaService } from '../prisma.service';

@Module({
  imports: [ConfigModule],
  controllers: [PaymentsController],
  providers: [
    PaymentsService,
    PrismaService,
    {
      provide: PAYMENT_PROVIDER,
      useFactory: (config: ConfigService) => {
        if (config.get('STRIPE_ENABLED') === 'true') {
          return new StripeProvider(config);
        }
        return new MockPaymentProvider();
      },
      inject: [ConfigService],
    },
  ],
  exports: [PaymentsService, PAYMENT_PROVIDER],
})
export class PaymentsModule {}
