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
Object.defineProperty(exports, "__esModule", { value: true });
exports.ContractsController = void 0;
const common_1 = require("@nestjs/common");
const passport_1 = require("@nestjs/passport");
const contracts_service_1 = require("./contracts.service");
const contract_pdf_service_1 = require("./contract-pdf.service");
const current_user_decorator_1 = require("../common/decorators/current-user.decorator");
const prisma_service_1 = require("../prisma.service");
const fs = require("fs");
const path = require("path");
let ContractsController = class ContractsController {
    constructor(contractsService, contractPdfService, prisma) {
        this.contractsService = contractsService;
        this.contractPdfService = contractPdfService;
        this.prisma = prisma;
        this.STAFF_DOMAINS = ['@flashbacklabs.com', '@flashbacklabs.inc'];
    }
    isStaffEmail(email) {
        return this.STAFF_DOMAINS.some((d) => email?.toLowerCase().endsWith(d));
    }
    async findAll(user) {
        const include = {
            projects_contracts_project_idToprojects: {
                select: { id: true, title: true, event_date: true, guest_count: true, status: true },
            },
        };
        if (this.isStaffEmail(user.email)) {
            return this.prisma.contracts.findMany({
                where: {
                    is_active: true,
                    projects_contracts_project_idToprojects: { deleted_at: null },
                },
                include,
                orderBy: { created_at: 'desc' },
            });
        }
        return this.prisma.contracts.findMany({
            where: {
                is_active: true,
                projects_contracts_project_idToprojects: {
                    deleted_at: null,
                    OR: [
                        { owner_user_id: user.userId },
                        { project_collaborators: { some: { user_id: user.userId } } },
                    ],
                },
            },
            include,
            orderBy: { created_at: 'desc' },
        });
    }
    async findOne(id, user) {
        const contract = await this.prisma.contracts.findFirst({
            where: { id },
            include: {
                projects_contracts_project_idToprojects: {
                    select: {
                        id: true,
                        title: true,
                        event_date: true,
                        guest_count: true,
                        status: true,
                        ai_event_summary: true,
                        venues: { select: { id: true, name: true, address: true } },
                    },
                },
            },
        });
        if (!contract)
            throw new common_1.NotFoundException(`Contract ${id} not found`);
        return contract;
    }
    async createContract(projectId, userId, body) {
        return this.contractsService.createVersion(userId, projectId, body);
    }
    async generatePdf(id, userId) {
        await this.contractsService.enqueuePdfGeneration(id, userId);
        return { message: 'PDF generation queued' };
    }
    async servePdf(id, res) {
        const contract = await this.prisma.contracts.findUnique({
            where: { id },
            select: { pdf_path: true },
        });
        if (!contract?.pdf_path) {
            throw new common_1.NotFoundException('PDF not yet generated for this contract');
        }
        const filePath = path.join(process.cwd(), contract.pdf_path);
        if (!fs.existsSync(filePath)) {
            throw new common_1.NotFoundException('PDF file not found on disk');
        }
        res.setHeader('Content-Type', 'application/pdf');
        res.setHeader('Content-Disposition', `inline; filename="contract-${id}.pdf"`);
        fs.createReadStream(filePath).pipe(res);
    }
    async previewPdf(id, user) {
        if (!this.isStaffEmail(user.email)) {
            throw new common_1.NotFoundException('Not found');
        }
        const pdfPath = await this.contractPdfService.generateSimpleContract(id);
        return { pdf_path: pdfPath };
    }
};
exports.ContractsController = ContractsController;
__decorate([
    (0, common_1.Get)('contracts'),
    __param(0, (0, current_user_decorator_1.CurrentUser)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object]),
    __metadata("design:returntype", Promise)
], ContractsController.prototype, "findAll", null);
__decorate([
    (0, common_1.Get)('contracts/:id'),
    __param(0, (0, common_1.Param)('id')),
    __param(1, (0, current_user_decorator_1.CurrentUser)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String, Object]),
    __metadata("design:returntype", Promise)
], ContractsController.prototype, "findOne", null);
__decorate([
    (0, common_1.Post)('projects/:projectId/contracts'),
    __param(0, (0, common_1.Param)('projectId')),
    __param(1, (0, current_user_decorator_1.CurrentUser)('userId')),
    __param(2, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String, String, Object]),
    __metadata("design:returntype", Promise)
], ContractsController.prototype, "createContract", null);
__decorate([
    (0, common_1.Post)('contracts/:id/generate-pdf'),
    __param(0, (0, common_1.Param)('id')),
    __param(1, (0, current_user_decorator_1.CurrentUser)('userId')),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String, String]),
    __metadata("design:returntype", Promise)
], ContractsController.prototype, "generatePdf", null);
__decorate([
    (0, common_1.Get)('contracts/:id/pdf'),
    __param(0, (0, common_1.Param)('id')),
    __param(1, (0, common_1.Res)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String, Object]),
    __metadata("design:returntype", Promise)
], ContractsController.prototype, "servePdf", null);
__decorate([
    (0, common_1.Post)('contracts/:id/preview-pdf'),
    __param(0, (0, common_1.Param)('id')),
    __param(1, (0, current_user_decorator_1.CurrentUser)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String, Object]),
    __metadata("design:returntype", Promise)
], ContractsController.prototype, "previewPdf", null);
exports.ContractsController = ContractsController = __decorate([
    (0, common_1.Controller)(),
    (0, common_1.UseGuards)((0, passport_1.AuthGuard)('jwt')),
    __metadata("design:paramtypes", [contracts_service_1.ContractsService,
        contract_pdf_service_1.ContractPdfService,
        prisma_service_1.PrismaService])
], ContractsController);
//# sourceMappingURL=contracts.controller.js.map