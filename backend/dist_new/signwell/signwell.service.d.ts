import { ConfigService } from '@nestjs/config';
export interface SignWellRecipient {
    email: string;
    name: string;
    role?: 'signer' | 'cc' | 'approver';
    order?: number;
}
export interface SignWellDocumentOptions {
    name: string;
    recipients: SignWellRecipient[];
    file_url?: string;
    file_base64?: string;
    test_mode?: boolean;
    redirect_url?: string;
    message?: string;
}
export interface SignWellDocument {
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
export declare class SignWellService {
    private readonly configService;
    private readonly logger;
    private readonly client;
    private readonly enabled;
    private readonly testMode;
    constructor(configService: ConfigService);
    sendDocumentForSignature(options: SignWellDocumentOptions): Promise<SignWellDocument>;
    getDocumentStatus(documentId: string): Promise<SignWellDocument>;
    cancelDocument(documentId: string): Promise<void>;
    resendSignatureRequest(documentId: string, recipientId: string): Promise<void>;
    downloadSignedDocument(documentId: string): Promise<Buffer>;
    private mockDocumentResponse;
}
