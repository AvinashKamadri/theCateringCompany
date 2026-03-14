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
exports.ContractsService = void 0;
const common_1 = require("@nestjs/common");
const bullmq_1 = require("@nestjs/bullmq");
const bullmq_2 = require("bullmq");
const crypto_1 = require("crypto");
const prisma_service_1 = require("../prisma.service");
const opensign_service_1 = require("../opensign/opensign.service");
let ContractsService = class ContractsService {
    constructor(prisma, pdfQueue, openSignService) {
        this.prisma = prisma;
        this.pdfQueue = pdfQueue;
        this.openSignService = openSignService;
    }
    async createVersion(userId, projectId, dto) {
        const contractGroupId = dto.contractGroupId ?? (0, crypto_1.randomUUID)();
        return this.prisma.$transaction(async (tx) => {
            const previousVersion = await tx.contracts.findFirst({
                where: { contract_group_id: contractGroupId },
                orderBy: { version_number: 'desc' },
                select: { id: true, version_number: true },
            });
            const nextVersionNumber = previousVersion
                ? previousVersion.version_number + 1
                : 1;
            const previousVersionId = previousVersion ? previousVersion.id : null;
            const contract = await tx.contracts.create({
                data: {
                    contract_group_id: contractGroupId,
                    version_number: nextVersionNumber,
                    previous_version_id: previousVersionId,
                    project_id: projectId,
                    status: dto.status ?? 'draft',
                    title: dto.title ?? null,
                    body: dto.body,
                    total_amount: dto.totalAmount ?? null,
                    is_active: true,
                    created_by: userId,
                },
            });
            return contract;
        });
    }
    async enqueuePdfGeneration(contractId, userId) {
        await this.pdfQueue.add('pdf_generation', {
            contractId,
            userId,
        });
    }
    async sendToSignWell(contractId, recipients, pdfUrl) {
        const contract = await this.prisma.contracts.findUnique({
            where: { id: contractId },
            include: {
                projects_contracts_project_idToprojects: {
                    select: {
                        title: true,
                        ai_event_summary: true,
                    },
                },
            },
        });
        if (!contract) {
            throw new Error(`Contract ${contractId} not found`);
        }
        let fileBase64;
        if (pdfUrl && !pdfUrl.startsWith('http')) {
            const fs = await Promise.resolve().then(() => require('fs/promises'));
            const path = await Promise.resolve().then(() => require('path'));
            const filePath = path.join(process.cwd(), pdfUrl);
            const fileBuffer = await fs.readFile(filePath);
            fileBase64 = fileBuffer.toString('base64');
            pdfUrl = undefined;
        }
        const openSignDoc = await this.openSignService.sendDocumentForSignature({
            name: contract.title || `Contract ${contractId}`,
            recipients,
            file_url: pdfUrl,
            file_base64: fileBase64,
            message: `Please review and sign the contract for ${contract.projects_contracts_project_idToprojects?.title || 'your event'}.`,
            redirect_url: `${process.env.CORS_ORIGIN}/contracts/${contractId}/signed`,
        });
        const existing = await this.prisma.contracts.findUnique({
            where: { id: contractId },
            select: { metadata: true },
        });
        const existingMeta = existing?.metadata || {};
        await this.prisma.contracts.update({
            where: { id: contractId },
            data: {
                status: 'sent',
                metadata: {
                    ...existingMeta,
                    opensign_document_id: openSignDoc.id,
                    opensign_status: openSignDoc.status,
                    opensign_signing_url: openSignDoc.signing_url,
                    sent_for_signature_at: new Date().toISOString(),
                },
            },
        });
        return openSignDoc;
    }
    async handleSignWellWebhook(event) {
        const { document_id, event_type, document } = event;
        const contract = await this.prisma.contracts.findFirst({
            where: {
                metadata: {
                    path: ['opensign_document_id'],
                    equals: document_id,
                },
            },
        });
        if (!contract) {
            console.warn(`Contract not found for SignWell document ${document_id}`);
            return;
        }
        switch (event_type) {
            case 'document.completed':
                const completedMetadata = contract.metadata || {};
                await this.prisma.contracts.update({
                    where: { id: contract.id },
                    data: {
                        status: 'signed',
                        metadata: {
                            ...completedMetadata,
                            signwell_status: 'completed',
                            signed_at: document.completed_at,
                        },
                    },
                });
                break;
            case 'document.declined':
                const declinedMetadata = contract.metadata || {};
                await this.prisma.contracts.update({
                    where: { id: contract.id },
                    data: {
                        status: 'rejected',
                        metadata: {
                            ...declinedMetadata,
                            signwell_status: 'declined',
                        },
                    },
                });
                break;
            case 'recipient.signed':
                const existingMetadata = contract.metadata || {};
                const updatedMetadata = {
                    ...existingMetadata,
                    recipient_signatures: [
                        ...(existingMetadata.recipient_signatures || []),
                        {
                            email: event.recipient.email,
                            signed_at: event.signed_at,
                        },
                    ],
                };
                await this.prisma.contracts.update({
                    where: { id: contract.id },
                    data: { metadata: updatedMetadata },
                });
                break;
        }
    }
};
exports.ContractsService = ContractsService;
exports.ContractsService = ContractsService = __decorate([
    (0, common_1.Injectable)(),
    __param(1, (0, bullmq_1.InjectQueue)('pdf_generation')),
    __metadata("design:paramtypes", [prisma_service_1.PrismaService,
        bullmq_2.Queue,
        opensign_service_1.OpenSignService])
], ContractsService);
//# sourceMappingURL=contracts.service.js.map