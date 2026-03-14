import { ConfigService } from '@nestjs/config';
export interface OpenSignRecipient {
    email: string;
    name: string;
    role?: 'signer' | 'cc' | 'approver';
    order?: number;
}
export interface OpenSignDocumentOptions {
    name: string;
    recipients: OpenSignRecipient[];
    file_base64?: string;
    file_url?: string;
    message?: string;
    redirect_url?: string;
}
export interface OpenSignDocument {
    id: string;
    name: string;
    status: 'pending' | 'completed' | 'declined' | 'expired';
    created_at: string;
    completed_at?: string;
    signing_url?: string;
    recipients: Array<{
        id: string;
        email: string;
        name: string;
        status: string;
        signing_url?: string;
    }>;
}
export declare class OpenSignService {
    private readonly configService;
    private readonly logger;
    private readonly client;
    private readonly enabled;
    private readonly signingBaseUrl;
    constructor(configService: ConfigService);
    sendDocumentForSignature(options: OpenSignDocumentOptions): Promise<OpenSignDocument>;
    getDocumentStatus(documentId: string): Promise<OpenSignDocument>;
    cancelDocument(documentId: string): Promise<void>;
    resendSignatureRequest(documentId: string, recipientId: string): Promise<void>;
    downloadSignedDocument(documentId: string): Promise<Buffer>;
    private mapStatus;
    private mockDocumentResponse;
}
