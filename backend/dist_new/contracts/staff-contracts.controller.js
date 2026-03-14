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
var StaffContractsController_1;
Object.defineProperty(exports, "__esModule", { value: true });
exports.StaffContractsController = void 0;
const common_1 = require("@nestjs/common");
const passport_1 = require("@nestjs/passport");
const staff_guard_1 = require("../common/guards/staff.guard");
const current_user_decorator_1 = require("../common/decorators/current-user.decorator");
const contracts_service_1 = require("./contracts.service");
const contract_pdf_service_1 = require("./contract-pdf.service");
const prisma_service_1 = require("../prisma.service");
const pricing_service_1 = require("../pricing/pricing.service");
let StaffContractsController = StaffContractsController_1 = class StaffContractsController {
    constructor(contractsService, contractPdfService, prisma, pricingService) {
        this.contractsService = contractsService;
        this.contractPdfService = contractPdfService;
        this.prisma = prisma;
        this.pricingService = pricingService;
        this.logger = new common_1.Logger(StaffContractsController_1.name);
    }
    async getAllContracts(user) {
        this.logger.log(`📋 [Staff] ${user.email} fetching all contracts`);
        const contracts = await this.prisma.contracts.findMany({
            where: { deleted_at: null },
            include: {
                projects_contracts_project_idToprojects: {
                    select: {
                        id: true,
                        title: true,
                        event_date: true,
                        guest_count: true,
                        status: true,
                    },
                },
            },
            orderBy: { created_at: 'desc' },
        });
        return contracts;
    }
    async getPendingContracts(user) {
        this.logger.log(`📋 [Staff] ${user.email} fetching pending contracts`);
        const contracts = await this.prisma.contracts.findMany({
            where: {
                status: 'pending_staff_approval',
                deleted_at: null,
            },
            include: {
                projects_contracts_project_idToprojects: {
                    select: {
                        id: true,
                        title: true,
                        event_date: true,
                        guest_count: true,
                        ai_event_summary: true,
                    },
                },
                users_contracts_created_byTousers: {
                    select: {
                        id: true,
                        email: true,
                    },
                },
            },
            orderBy: {
                created_at: 'desc',
            },
        });
        this.logger.log(`📊 [Staff] Found ${contracts.length} pending contracts`);
        return {
            contracts,
            count: contracts.length,
        };
    }
    async getContractForReview(contractId, user) {
        this.logger.log(`📄 [Staff] ${user.email} reviewing contract ${contractId}`);
        const contract = await this.prisma.contracts.findUnique({
            where: { id: contractId },
            include: {
                projects_contracts_project_idToprojects: {
                    select: {
                        id: true,
                        title: true,
                        event_date: true,
                        event_end_date: true,
                        guest_count: true,
                        ai_event_summary: true,
                        venues: {
                            select: {
                                name: true,
                                address: true,
                            },
                        },
                    },
                },
                users_contracts_created_byTousers: {
                    select: {
                        id: true,
                        email: true,
                        primary_phone: true,
                    },
                },
            },
        });
        if (!contract) {
            this.logger.warn(`⚠️ [Staff] Contract ${contractId} not found`);
            throw new Error('Contract not found');
        }
        return contract;
    }
    async approveContract(contractId, user, body) {
        try {
            this.logger.log(`✅ [Staff] ${user.email} approving contract ${contractId}`);
            console.log(`[DEBUG] Step 1: Starting approval for contract ${contractId}`);
            console.log('[DEBUG] Step 2: Fetching contract from database...');
            const contract = await this.prisma.contracts.findUnique({
                where: { id: contractId },
                include: {
                    projects_contracts_project_idToprojects: {
                        select: {
                            ai_event_summary: true,
                        },
                    },
                    users_contracts_created_byTousers: {
                        select: {
                            email: true,
                        },
                    },
                },
            });
            if (!contract) {
                console.log('[DEBUG] Step 3: ERROR - Contract not found!');
                throw new Error('Contract not found');
            }
            console.log('[DEBUG] Step 3: Contract found, extracting client info...');
            const contractBody = contract.body;
            console.log('[DEBUG] Step 4: Contract body:', JSON.stringify(contractBody, null, 2));
            const rawSummary = contract.projects_contracts_project_idToprojects?.ai_event_summary;
            const aiEventData = !rawSummary
                ? {}
                : typeof rawSummary === 'string'
                    ? JSON.parse(rawSummary)
                    : rawSummary;
            console.log('[DEBUG] Step 5: AI event data:', JSON.stringify(aiEventData, null, 2));
            const clientEmail = contractBody?.client_info?.email ||
                contractBody?.slots?.email ||
                aiEventData.contact_email ||
                contract.users_contracts_created_byTousers?.email;
            const clientName = contractBody?.client_info?.name ||
                contractBody?.slots?.name ||
                aiEventData.client_name ||
                contract.users_contracts_created_byTousers?.email?.split('@')[0] ||
                'Client';
            console.log('[DEBUG] Step 6: Extracted - Email:', clientEmail, 'Name:', clientName);
            if (!clientEmail) {
                console.log('[DEBUG] Step 7: ERROR - No email found anywhere for contract!');
                throw new Error('Cannot determine client email — no email in contract body or creator account');
            }
            const existingMetadata = contract.metadata || {};
            const approvalMetadata = {
                ...existingMetadata,
                approved_by: user.email,
                approved_at: new Date().toISOString(),
                approval_message: body.message,
                adjustments: body.adjustments,
            };
            await this.prisma.contracts.update({
                where: { id: contractId },
                data: { status: 'approved', metadata: approvalMetadata },
            });
            this.logger.log(`✅ [Staff] Contract ${contractId} approved by ${user.email}`);
            this.logger.log(`📧 [Staff] Preparing to send to OpenSign for client: ${clientName} (${clientEmail})`);
            console.log('[DEBUG] Step 8: Contract updated to approved status');
            this.logger.log(`📄 [Staff] Regenerating PDF with latest pricing for contract ${contractId}`);
            const pdfPath = await this.contractPdfService.generateSimpleContract(contractId);
            console.log('[DEBUG] Step 12: Sending to OpenSign...');
            try {
                const signWellDoc = await this.contractsService.sendToSignWell(contractId, [
                    {
                        email: clientEmail,
                        name: clientName,
                        role: 'signer',
                    },
                ], pdfPath);
                console.log('[DEBUG] Step 13: OpenSign response received:', signWellDoc);
                this.logger.log(`✅ [Staff] Contract ${contractId} sent to OpenSign successfully`);
                this.logger.log(`🔗 [Staff] OpenSign document ID: ${signWellDoc.id}`);
                this.logger.log(`📨 [Staff] Client will receive email at: ${clientEmail}`);
                return {
                    success: true,
                    message: 'Contract approved and sent to client for signature',
                    opensign_document_id: signWellDoc.id,
                    signing_url: signWellDoc.signing_url,
                };
            }
            catch (error) {
                console.log('[DEBUG] ERROR in OpenSign call:', error);
                this.logger.error(`❌ [Staff] Failed to send contract ${contractId} to OpenSign`, error.message);
                this.logger.error(`❌ [Staff] Error stack:`, error.stack);
                await this.prisma.contracts.update({
                    where: { id: contractId },
                    data: { status: 'pending_staff_approval' },
                });
                throw new Error(`Failed to send to OpenSign: ${error.message}`);
            }
        }
        catch (error) {
            console.log('[DEBUG] FATAL ERROR in approval:', error);
            this.logger.error(`❌ [Staff] Approval failed for contract ${contractId}`, error.message);
            this.logger.error(`❌ [Staff] Error details:`, error);
            throw error;
        }
    }
    async rejectContract(contractId, user, body) {
        this.logger.log(`❌ [Staff] ${user.email} rejecting contract ${contractId}`);
        this.logger.log(`📝 [Staff] Reason: ${body.reason}`);
        const contract = await this.prisma.contracts.findUnique({
            where: { id: contractId },
            select: { metadata: true },
        });
        const existingMetadata = contract?.metadata || {};
        await this.prisma.contracts.update({
            where: { id: contractId },
            data: {
                status: 'rejected',
                metadata: {
                    ...existingMetadata,
                    rejected_by: user.email,
                    rejected_at: new Date().toISOString(),
                    rejection_reason: body.reason,
                },
            },
        });
        this.logger.log(`✅ [Staff] Contract ${contractId} rejected`);
        return {
            success: true,
            message: 'Contract rejected',
        };
    }
    async calculatePricing(contractId, user) {
        this.logger.log(`💰 [Staff] ${user.email} calculating pricing for contract ${contractId}`);
        const contract = await this.prisma.contracts.findUnique({
            where: { id: contractId },
            include: {
                projects_contracts_project_idToprojects: {
                    select: { guest_count: true },
                },
            },
        });
        if (!contract)
            throw new Error('Contract not found');
        const body = contract.body || {};
        const eventDetails = body.event_details || {};
        const menuData = body.menu || {};
        const additional = body.additional || {};
        const slots = body.slots || {};
        const guestCount = Number(eventDetails.guest_count || slots.guest_count ||
            contract.projects_contracts_project_idToprojects?.guest_count || 50);
        const eventType = eventDetails.type || slots.event_type || '';
        const serviceType = eventDetails.service_type || slots.service_type || '';
        const menuItems = menuData.items?.map((i) => typeof i === 'string' ? i : i.name || i).filter(Boolean) || [];
        const addons = additional.addons || [];
        const breakdown = await this.pricingService.calculateEventPricing({
            guestCount,
            eventType,
            serviceType,
            menuItems,
            addons,
        });
        this.logger.log(`✅ [Staff] Pricing calculated: ${breakdown.lineItems.length} line items, grand total $${breakdown.grandTotal}`);
        return breakdown;
    }
    async updatePricing(contractId, user, body) {
        this.logger.log(`💰 [Staff] ${user.email} updating pricing for contract ${contractId}`);
        const contract = await this.prisma.contracts.findUnique({
            where: { id: contractId },
        });
        if (!contract) {
            throw new Error('Contract not found');
        }
        const existingBody = contract.body;
        const updatedBody = {
            ...existingBody,
            pricing: body.pricing,
        };
        const existingMetadata = contract.metadata || {};
        await this.prisma.contracts.update({
            where: { id: contractId },
            data: {
                body: updatedBody,
                total_amount: body.pricing.total ?? body.pricing.subtotal ?? contract.total_amount,
                metadata: {
                    ...existingMetadata,
                    pricing_updated_by: user.email,
                    pricing_updated_at: new Date().toISOString(),
                },
            },
        });
        this.logger.log(`✅ [Staff] Pricing updated for contract ${contractId}`);
        return {
            success: true,
            message: 'Pricing updated successfully',
        };
    }
};
exports.StaffContractsController = StaffContractsController;
__decorate([
    (0, common_1.Get)(),
    __param(0, (0, current_user_decorator_1.CurrentUser)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object]),
    __metadata("design:returntype", Promise)
], StaffContractsController.prototype, "getAllContracts", null);
__decorate([
    (0, common_1.Get)('pending'),
    __param(0, (0, current_user_decorator_1.CurrentUser)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object]),
    __metadata("design:returntype", Promise)
], StaffContractsController.prototype, "getPendingContracts", null);
__decorate([
    (0, common_1.Get)(':id'),
    __param(0, (0, common_1.Param)('id')),
    __param(1, (0, current_user_decorator_1.CurrentUser)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String, Object]),
    __metadata("design:returntype", Promise)
], StaffContractsController.prototype, "getContractForReview", null);
__decorate([
    (0, common_1.Post)(':id/approve'),
    __param(0, (0, common_1.Param)('id')),
    __param(1, (0, current_user_decorator_1.CurrentUser)()),
    __param(2, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String, Object, Object]),
    __metadata("design:returntype", Promise)
], StaffContractsController.prototype, "approveContract", null);
__decorate([
    (0, common_1.Post)(':id/reject'),
    __param(0, (0, common_1.Param)('id')),
    __param(1, (0, current_user_decorator_1.CurrentUser)()),
    __param(2, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String, Object, Object]),
    __metadata("design:returntype", Promise)
], StaffContractsController.prototype, "rejectContract", null);
__decorate([
    (0, common_1.Post)(':id/calculate-pricing'),
    __param(0, (0, common_1.Param)('id')),
    __param(1, (0, current_user_decorator_1.CurrentUser)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String, Object]),
    __metadata("design:returntype", Promise)
], StaffContractsController.prototype, "calculatePricing", null);
__decorate([
    (0, common_1.Patch)(':id/pricing'),
    __param(0, (0, common_1.Param)('id')),
    __param(1, (0, current_user_decorator_1.CurrentUser)()),
    __param(2, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String, Object, Object]),
    __metadata("design:returntype", Promise)
], StaffContractsController.prototype, "updatePricing", null);
exports.StaffContractsController = StaffContractsController = StaffContractsController_1 = __decorate([
    (0, common_1.UseGuards)((0, passport_1.AuthGuard)('jwt'), staff_guard_1.StaffGuard),
    (0, common_1.Controller)('staff/contracts'),
    __metadata("design:paramtypes", [contracts_service_1.ContractsService,
        contract_pdf_service_1.ContractPdfService,
        prisma_service_1.PrismaService,
        pricing_service_1.PricingService])
], StaffContractsController);
//# sourceMappingURL=staff-contracts.controller.js.map