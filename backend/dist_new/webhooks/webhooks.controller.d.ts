import { Request } from 'express';
import { WebhooksService } from './webhooks.service';
export declare class WebhooksController {
    private readonly webhooksService;
    constructor(webhooksService: WebhooksService);
    handleStripeWebhook(req: Request, signature: string): Promise<{
        received: boolean;
    }>;
    handleGenericWebhook(provider: string, req: Request): Promise<{
        received: boolean;
    }>;
}
