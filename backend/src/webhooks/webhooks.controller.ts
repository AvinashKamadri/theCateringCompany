import {
  Controller,
  Post,
  Param,
  Req,
  Headers,
  HttpCode,
  HttpStatus,
} from '@nestjs/common';
import { Request } from 'express';
import { Public } from '../common/decorators/public.decorator';
import { WebhooksService } from './webhooks.service';

@Controller('webhooks')
export class WebhooksController {
  constructor(private readonly webhooksService: WebhooksService) {}

  @Public()
  @Post('stripe')
  @HttpCode(HttpStatus.OK)
  async handleStripeWebhook(
    @Req() req: Request,
    @Headers('stripe-signature') signature: string,
  ) {
    const rawBody = (req as any).rawBody as Buffer;
    await this.webhooksService.handleStripeWebhook(rawBody, signature);
    return { received: true };
  }

  @Public()
  @Post('docuseal')
  @HttpCode(HttpStatus.OK)
  async handleDocuSealWebhook(@Req() req: Request) {
    const rawBody = (req as any).rawBody as Buffer;
    await this.webhooksService.handleDocuSealWebhook(rawBody);
    return { received: true };
  }

  @Public()
  @Post(':provider')
  @HttpCode(HttpStatus.OK)
  async handleGenericWebhook(
    @Param('provider') provider: string,
    @Req() req: Request,
  ) {
    const rawBody = (req as any).rawBody as Buffer;
    await this.webhooksService.handleGenericWebhook(provider, rawBody);
    return { received: true };
  }
}
