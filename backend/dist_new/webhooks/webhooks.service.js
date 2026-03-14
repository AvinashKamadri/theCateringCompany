"use strict";
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};
var __param = (this && this.__param) || function (paramIndex, decorator) {
    return function (target, key) { decorator(target, key, paramIndex); }
};
var WebhooksService_1;
Object.defineProperty(exports, "__esModule", { value: true });
exports.WebhooksService = void 0;
const common_1 = require("@nestjs/common");
const config_1 = require("@nestjs/config");
const bullmq_1 = require("@nestjs/bullmq");
const bullmq_2 = require("bullmq");
const crypto_1 = require("crypto");
const prisma_service_1 = require("../prisma.service");
const payment_provider_interface_1 = require("../payments/payment-provider.interface");
let WebhooksService = WebhooksService_1 = class WebhooksService {
    constructor(prisma, config, paymentProvider, webhooksQueue) {
        this.prisma = prisma;
        this.config = config;
        this.paymentProvider = paymentProvider;
        this.webhooksQueue = webhooksQueue;
        this.logger = new common_1.Logger(WebhooksService_1.name);
    }
    async handleStripeWebhook(rawBody, signature) {
        const stripeEnabled = this.config.get('STRIPE_ENABLED') === 'true';
        let event;
        let eventType;
        let externalEventId;
        if (stripeEnabled) {
            const webhookSecret = this.config.get('STRIPE_WEBHOOK_SECRET');
            event = this.paymentProvider.constructWebhookEvent(rawBody, signature, webhookSecret);
            eventType = event.type;
            externalEventId = event.id;
        }
        else {
            event = JSON.parse(rawBody.toString());
            eventType = event.type;
            externalEventId = event.id;
        }
        const idempotencyHash = (0, crypto_1.createHash)('sha256')
            .update(rawBody)
            .digest('hex');
        const webhookEvent = await this.prisma.webhook_events.create({
            data: {
                provider: 'stripe',
                external_event_id: externalEventId || 'unknown',
                event_type: eventType,
                payload: event,
                idempotency_hash: idempotencyHash,
                status: 'pending',
            },
        });
        await this.webhooksQueue.add('webhooks', {
            webhookEventId: webhookEvent.id,
        });
        this.logger.log(`Stripe webhook event ${webhookEvent.id} persisted and enqueued (type: ${eventType})`);
    }
    async handleGenericWebhook(provider, rawBody) {
        let payload;
        try {
            payload = JSON.parse(rawBody.toString());
        }
        catch {
            payload = { raw: rawBody.toString() };
        }
        const externalEventId = payload?.id ?? undefined;
        const idempotencyHash = (0, crypto_1.createHash)('sha256')
            .update(rawBody)
            .digest('hex');
        const webhookEvent = await this.prisma.webhook_events.create({
            data: {
                provider,
                external_event_id: externalEventId,
                event_type: payload?.type ?? payload?.event_type,
                payload,
                idempotency_hash: idempotencyHash,
                status: 'pending',
            },
        });
        await this.webhooksQueue.add('webhooks', {
            webhookEventId: webhookEvent.id,
        });
        this.logger.log(`Generic webhook event ${webhookEvent.id} persisted and enqueued (provider: ${provider})`);
    }
};
exports.WebhooksService = WebhooksService;
exports.WebhooksService = WebhooksService = WebhooksService_1 = __decorate([
    (0, common_1.Injectable)(),
    __param(2, (0, common_1.Inject)(payment_provider_interface_1.PAYMENT_PROVIDER)),
    __param(3, (0, bullmq_1.InjectQueue)('webhooks')),
    __metadata("design:paramtypes", [prisma_service_1.PrismaService,
        config_1.ConfigService, Object, bullmq_2.Queue])
], WebhooksService);
//# sourceMappingURL=webhooks.service.js.map