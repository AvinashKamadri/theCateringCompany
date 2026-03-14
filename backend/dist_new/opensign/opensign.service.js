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
var OpenSignService_1;
Object.defineProperty(exports, "__esModule", { value: true });
exports.OpenSignService = void 0;
const common_1 = require("@nestjs/common");
const config_1 = require("@nestjs/config");
const axios_1 = require("axios");
let OpenSignService = OpenSignService_1 = class OpenSignService {
    constructor(configService) {
        this.configService = configService;
        this.logger = new common_1.Logger(OpenSignService_1.name);
        this.enabled =
            this.configService.get('DOCUSEAL_ENABLED') === 'true' ||
                this.configService.get('OPENSIGN_ENABLED') === 'true';
        const apiKey = this.configService.get('DOCUSEAL_API_KEY') ||
            this.configService.get('OPENSIGN_API_KEY');
        const apiUrl = this.configService.get('DOCUSEAL_API_URL') || 'https://api.docuseal.co';
        this.signingBaseUrl =
            this.configService.get('DOCUSEAL_SIGNING_URL') || 'https://docuseal.co';
        this.client = axios_1.default.create({
            baseURL: apiUrl,
            headers: {
                'X-Auth-Token': apiKey,
                'Content-Type': 'application/json',
            },
            timeout: 60000,
        });
        this.logger.log(`DocuSeal service initialized (enabled: ${this.enabled}, api: ${apiUrl})`);
    }
    async sendDocumentForSignature(options) {
        if (!this.enabled) {
            this.logger.warn('DocuSeal is disabled, returning mock response');
            return this.mockDocumentResponse(options);
        }
        try {
            this.logger.log(`Creating DocuSeal template: ${options.name}`);
            const templatePayload = { name: options.name };
            if (options.file_base64) {
                templatePayload.documents = [
                    { name: `${options.name}.pdf`, file: options.file_base64 },
                ];
            }
            else if (options.file_url) {
                templatePayload.documents = [
                    { name: `${options.name}.pdf`, url: options.file_url },
                ];
            }
            const templateResponse = await this.client.post('/templates/pdf', templatePayload);
            const template = templateResponse.data;
            const templateId = template.id;
            this.logger.log(`Template created: ID ${templateId}`);
            const hasSignatureField = (template.fields || []).some((f) => f.type === 'signature');
            if (!hasSignatureField) {
                const firstSubmitterUuid = template.submitters?.[0]?.uuid;
                const firstDocUuid = template.schema?.[0]?.attachment_uuid;
                if (firstSubmitterUuid && firstDocUuid) {
                    this.logger.log('Adding signature field to template...');
                    await this.client.put(`/templates/${templateId}`, {
                        fields: [
                            {
                                name: 'Signature',
                                type: 'signature',
                                required: true,
                                submitter_uuid: firstSubmitterUuid,
                                areas: [
                                    {
                                        x: 0.08,
                                        y: 0.88,
                                        w: 0.35,
                                        h: 0.07,
                                        attachment_uuid: firstDocUuid,
                                        page: 0,
                                    },
                                ],
                            },
                            {
                                name: 'Date',
                                type: 'date',
                                required: false,
                                submitter_uuid: firstSubmitterUuid,
                                areas: [
                                    {
                                        x: 0.55,
                                        y: 0.88,
                                        w: 0.25,
                                        h: 0.05,
                                        attachment_uuid: firstDocUuid,
                                        page: 0,
                                    },
                                ],
                            },
                        ],
                    });
                    this.logger.log('Signature field added');
                }
            }
            const submissionPayload = {
                template_id: templateId,
                send_email: true,
                submitters: options.recipients.map((r) => ({
                    email: r.email,
                    name: r.name,
                    role: 'First Submitter',
                })),
            };
            if (options.message) {
                submissionPayload.message = {
                    subject: `Please sign: ${options.name}`,
                    body: options.message,
                };
            }
            this.logger.log(`Creating submission for: ${options.recipients.map((r) => r.email).join(', ')}`);
            console.log('[DEBUG] DocuSeal submission payload:', JSON.stringify(submissionPayload, null, 2));
            const submissionResponse = await this.client.post('/submissions', submissionPayload);
            const submitters = Array.isArray(submissionResponse.data)
                ? submissionResponse.data
                : [submissionResponse.data];
            const firstSubmitter = submitters[0];
            const submissionId = String(firstSubmitter.submission_id || firstSubmitter.id);
            this.logger.log(`Submission created: ID ${submissionId}, slug: ${firstSubmitter.slug}`);
            this.logger.log(`Signing link: ${this.signingBaseUrl}/s/${firstSubmitter.slug}`);
            return {
                id: submissionId,
                name: options.name,
                status: 'pending',
                created_at: new Date().toISOString(),
                signing_url: `${this.signingBaseUrl}/s/${firstSubmitter.slug}`,
                recipients: submitters.map((s) => ({
                    id: String(s.id),
                    email: s.email,
                    name: s.name,
                    status: s.status || 'awaiting',
                    signing_url: `${this.signingBaseUrl}/s/${s.slug}`,
                })),
            };
        }
        catch (error) {
            this.logger.error('Failed to send document via DocuSeal', error.response?.data || error.message);
            console.log('[DEBUG] DocuSeal API error:', error.response?.data || error.message);
            console.log('[DEBUG] DocuSeal error details:', {
                status: error.response?.status,
                data: error.response?.data,
            });
            throw new Error(`DocuSeal API error: ${JSON.stringify(error.response?.data) || error.message}`);
        }
    }
    async getDocumentStatus(documentId) {
        if (!this.enabled) {
            return this.mockDocumentResponse({ name: 'Mock Document', recipients: [] });
        }
        try {
            const response = await this.client.get(`/submissions/${documentId}`);
            const data = response.data;
            return {
                id: String(data.id),
                name: data.template?.name || 'Contract',
                status: this.mapStatus(data.status),
                created_at: data.created_at || new Date().toISOString(),
                completed_at: data.completed_at,
                recipients: (data.submitters || []).map((s) => ({
                    id: String(s.id),
                    email: s.email,
                    name: s.name,
                    status: s.status || 'awaiting',
                    signing_url: `${this.signingBaseUrl}/s/${s.slug}`,
                })),
            };
        }
        catch (error) {
            throw new Error(`DocuSeal API error: ${error.response?.data?.message || error.message}`);
        }
    }
    async cancelDocument(documentId) {
        if (!this.enabled)
            return;
        try {
            await this.client.delete(`/submissions/${documentId}`);
            this.logger.log(`Submission cancelled: ${documentId}`);
        }
        catch (error) {
            throw new Error(`DocuSeal API error: ${error.response?.data?.message || error.message}`);
        }
    }
    async resendSignatureRequest(documentId, recipientId) {
        this.logger.warn(`Resend not supported by DocuSeal (submission: ${documentId}, submitter: ${recipientId})`);
    }
    async downloadSignedDocument(documentId) {
        if (!this.enabled) {
            return Buffer.from('Mock PDF content');
        }
        try {
            const response = await this.client.get(`/submissions/${documentId}/download`, { responseType: 'arraybuffer' });
            return Buffer.from(response.data);
        }
        catch (error) {
            throw new Error(`DocuSeal API error: ${error.response?.data?.message || error.message}`);
        }
    }
    mapStatus(status) {
        switch (status) {
            case 'completed': return 'completed';
            case 'declined': return 'declined';
            case 'expired': return 'expired';
            default: return 'pending';
        }
    }
    mockDocumentResponse(options) {
        const docId = `docuseal_mock_${Date.now()}`;
        return {
            id: docId,
            name: options.name,
            status: 'pending',
            created_at: new Date().toISOString(),
            signing_url: `https://docuseal.co/s/${docId}`,
            recipients: options.recipients.map((r, index) => ({
                id: `recipient_${index}`,
                email: r.email,
                name: r.name,
                status: 'awaiting',
                signing_url: `https://docuseal.co/s/${docId}_${index}`,
            })),
        };
    }
};
exports.OpenSignService = OpenSignService;
exports.OpenSignService = OpenSignService = OpenSignService_1 = __decorate([
    (0, common_1.Injectable)(),
    __metadata("design:paramtypes", [config_1.ConfigService])
], OpenSignService);
//# sourceMappingURL=opensign.service.js.map