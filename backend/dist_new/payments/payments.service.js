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
var PaymentsService_1;
Object.defineProperty(exports, "__esModule", { value: true });
exports.PaymentsService = void 0;
const common_1 = require("@nestjs/common");
const config_1 = require("@nestjs/config");
const prisma_service_1 = require("../prisma.service");
const payment_provider_interface_1 = require("./payment-provider.interface");
let PaymentsService = PaymentsService_1 = class PaymentsService {
    constructor(paymentProvider, prisma, config) {
        this.paymentProvider = paymentProvider;
        this.prisma = prisma;
        this.config = config;
        this.logger = new common_1.Logger(PaymentsService_1.name);
    }
    async createPaymentIntent(clientId, projectId, amount, currency, idempotencyKey) {
        const stripeEnabled = this.config.get('STRIPE_ENABLED') === 'true';
        const paymentRequest = await this.prisma.payment_requests.create({
            data: {
                client_id: clientId,
                idempotency_key: idempotencyKey,
                status: 'pending',
            },
        });
        if (!stripeEnabled) {
            const mockId = `mock_pi_${idempotencyKey}`;
            await this.prisma.payments.create({
                data: {
                    project_id: projectId,
                    payment_request_id: paymentRequest.id,
                    gateway_payment_intent_id: mockId,
                    amount,
                    currency,
                    status: 'pending',
                    idempotency_key: idempotencyKey,
                },
            });
            this.logger.log(`Mock payment intent created for request ${paymentRequest.id}`);
            return {
                clientSecret: `mock_secret_${idempotencyKey}`,
                paymentRequestId: paymentRequest.id,
            };
        }
        const { id, clientSecret } = await this.paymentProvider.createPaymentIntent(amount, currency, idempotencyKey, {
            projectId,
            paymentRequestId: paymentRequest.id,
        });
        await this.prisma.payments.create({
            data: {
                project_id: projectId,
                payment_request_id: paymentRequest.id,
                gateway_payment_intent_id: id,
                amount,
                currency,
                status: 'pending',
                idempotency_key: idempotencyKey,
            },
        });
        this.logger.log(`Stripe payment intent ${id} created for request ${paymentRequest.id}`);
        return { clientSecret, paymentRequestId: paymentRequest.id };
    }
};
exports.PaymentsService = PaymentsService;
exports.PaymentsService = PaymentsService = PaymentsService_1 = __decorate([
    (0, common_1.Injectable)(),
    __param(0, (0, common_1.Inject)(payment_provider_interface_1.PAYMENT_PROVIDER)),
    __metadata("design:paramtypes", [Object, prisma_service_1.PrismaService,
        config_1.ConfigService])
], PaymentsService);
//# sourceMappingURL=payments.service.js.map