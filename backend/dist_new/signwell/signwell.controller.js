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
var SignWellController_1;
Object.defineProperty(exports, "__esModule", { value: true });
exports.SignWellController = void 0;
const common_1 = require("@nestjs/common");
const public_decorator_1 = require("../common/decorators/public.decorator");
const contracts_service_1 = require("../contracts/contracts.service");
let SignWellController = SignWellController_1 = class SignWellController {
    constructor(contractsService) {
        this.contractsService = contractsService;
        this.logger = new common_1.Logger(SignWellController_1.name);
    }
    async handleWebhook(event, signature) {
        this.logger.log(`Received SignWell webhook: ${event.event_type}`);
        this.logger.debug(`Event data:`, JSON.stringify(event, null, 2));
        try {
            await this.contractsService.handleSignWellWebhook(event);
            return {
                success: true,
                message: 'Webhook processed successfully',
            };
        }
        catch (error) {
            this.logger.error('Failed to process SignWell webhook', error.message);
            throw error;
        }
    }
    verifySignature(event, signature) {
        return true;
    }
};
exports.SignWellController = SignWellController;
__decorate([
    (0, public_decorator_1.Public)(),
    (0, common_1.Post)('webhook'),
    __param(0, (0, common_1.Body)()),
    __param(1, (0, common_1.Headers)('x-signwell-signature')),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object, String]),
    __metadata("design:returntype", Promise)
], SignWellController.prototype, "handleWebhook", null);
exports.SignWellController = SignWellController = SignWellController_1 = __decorate([
    (0, common_1.Controller)('signwell'),
    __metadata("design:paramtypes", [contracts_service_1.ContractsService])
], SignWellController);
//# sourceMappingURL=signwell.controller.js.map