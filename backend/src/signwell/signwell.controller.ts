import { Controller, Post, Body, Headers, Logger } from '@nestjs/common';
import { Public } from '../common/decorators/public.decorator';
import { ContractsService } from '../contracts/contracts.service';

@Controller('signwell')
export class SignWellController {
  private readonly logger = new Logger(SignWellController.name);

  constructor(private readonly contractsService: ContractsService) {}

  /**
   * POST /signwell/webhook
   * Handle webhooks from SignWell
   * This endpoint is public (no auth required) since SignWell sends webhooks
   */
  @Public()
  @Post('webhook')
  async handleWebhook(
    @Body() event: any,
    @Headers('x-signwell-signature') signature: string,
  ) {
    this.logger.log(`Received SignWell webhook: ${event.event_type}`);
    this.logger.debug(`Event data:`, JSON.stringify(event, null, 2));

    try {
      // TODO: Verify webhook signature for security
      // const isValid = this.verifySignature(event, signature);
      // if (!isValid) {
      //   throw new Error('Invalid webhook signature');
      // }

      // Process the webhook
      await this.contractsService.handleSignWellWebhook(event);

      return {
        success: true,
        message: 'Webhook processed successfully',
      };
    } catch (error: any) {
      this.logger.error('Failed to process SignWell webhook', error.message);
      throw error;
    }
  }

  /**
   * Verify SignWell webhook signature (implement based on SignWell docs)
   */
  private verifySignature(event: any, signature: string): boolean {
    // TODO: Implement signature verification based on SignWell documentation
    // This prevents malicious actors from sending fake webhooks
    return true;
  }
}
