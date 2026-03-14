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
var OpenSignController_1;
Object.defineProperty(exports, "__esModule", { value: true });
exports.OpenSignController = void 0;
const common_1 = require("@nestjs/common");
const opensign_service_1 = require("./opensign.service");
let OpenSignController = OpenSignController_1 = class OpenSignController {
    constructor(openSignService) {
        this.openSignService = openSignService;
        this.logger = new common_1.Logger(OpenSignController_1.name);
    }
    async handleWebhook(body, signature) {
        this.logger.log('Received OpenSign webhook');
        console.log('[DEBUG] OpenSign webhook payload:', JSON.stringify(body, null, 2));
        console.log('[DEBUG] OpenSign webhook signature:', signature);
        try {
            const eventType = body.event || body.type;
            const documentId = body.document?.id || body.documentId;
            this.logger.log(`Webhook event: ${eventType} for document ${documentId}`);
            switch (eventType) {
                case 'document.signed':
                case 'document.completed':
                    this.logger.log(`Document ${documentId} has been signed/completed`);
                    break;
                case 'document.declined':
                    this.logger.warn(`Document ${documentId} was declined`);
                    break;
                case 'document.expired':
                    this.logger.warn(`Document ${documentId} has expired`);
                    break;
                case 'signer.signed':
                    this.logger.log(`Signer completed signing for document ${documentId}`);
                    break;
                default:
                    this.logger.warn(`Unknown webhook event type: ${eventType}`);
            }
            return { success: true, message: 'Webhook received' };
        }
        catch (error) {
            this.logger.error('Error processing OpenSign webhook', error);
            throw error;
        }
    }
};
exports.OpenSignController = OpenSignController;
__decorate([
    (0, common_1.Post)('webhook'),
    __param(0, (0, common_1.Body)()),
    __param(1, (0, common_1.Headers)('x-opensign-signature')),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object, String]),
    __metadata("design:returntype", Promise)
], OpenSignController.prototype, "handleWebhook", null);
exports.OpenSignController = OpenSignController = OpenSignController_1 = __decorate([
    (0, common_1.Controller)('opensign'),
    __metadata("design:paramtypes", [opensign_service_1.OpenSignService])
], OpenSignController);
//# sourceMappingURL=opensign.controller.js.map