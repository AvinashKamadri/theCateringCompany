import { Controller, Post, Body, Logger, Headers } from '@nestjs/common';
import { OpenSignService } from './opensign.service';

@Controller('opensign')
export class OpenSignController {
  private readonly logger = new Logger(OpenSignController.name);

  constructor(private readonly openSignService: OpenSignService) {}

  /**
   * POST /opensign/webhook
   * Handle webhook notifications from OpenSign
   */
  @Post('webhook')
  async handleWebhook(
    @Body() body: any,
    @Headers('x-opensign-signature') signature?: string,
  ) {
    this.logger.log('Received OpenSign webhook');
    console.log('[DEBUG] OpenSign webhook payload:', JSON.stringify(body, null, 2));
    console.log('[DEBUG] OpenSign webhook signature:', signature);

    try {
      // TODO: Verify webhook signature if provided

      const eventType = body.event || body.type;
      const documentId = body.document?.id || body.documentId;

      this.logger.log(`Webhook event: ${eventType} for document ${documentId}`);

      switch (eventType) {
        case 'document.signed':
        case 'document.completed':
          this.logger.log(`Document ${documentId} has been signed/completed`);
          // TODO: Update contract status in database
          break;

        case 'document.declined':
          this.logger.warn(`Document ${documentId} was declined`);
          // TODO: Update contract status to declined
          break;

        case 'document.expired':
          this.logger.warn(`Document ${documentId} has expired`);
          // TODO: Update contract status to expired
          break;

        case 'signer.signed':
          this.logger.log(`Signer completed signing for document ${documentId}`);
          // TODO: Update signer status in contract metadata
          break;

        default:
          this.logger.warn(`Unknown webhook event type: ${eventType}`);
      }

      return { success: true, message: 'Webhook received' };
    } catch (error) {
      this.logger.error('Error processing OpenSign webhook', error);
      throw error;
    }
  }
}
