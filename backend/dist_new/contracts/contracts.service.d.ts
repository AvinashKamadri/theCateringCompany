import { Queue } from 'bullmq';
import { PrismaService } from '../prisma.service';
import { OpenSignService } from '../opensign/opensign.service';
export declare class ContractsService {
    private readonly prisma;
    private readonly pdfQueue;
    private readonly openSignService;
    constructor(prisma: PrismaService, pdfQueue: Queue, openSignService: OpenSignService);
    createVersion(userId: string, projectId: string, dto: {
        title?: string;
        body: any;
        status?: string;
        totalAmount?: number;
        contractGroupId?: string;
    }): Promise<{
        id: string;
        contract_group_id: string;
        version_number: number;
        status: import(".prisma/client").$Enums.contract_status;
        title: string | null;
        body: import("@prisma/client/runtime/library").JsonValue;
        pdf_path: string | null;
        total_amount: import("@prisma/client/runtime/library").Decimal | null;
        change_reason: string | null;
        metadata: import("@prisma/client/runtime/library").JsonValue | null;
        is_active: boolean;
        ai_generated: boolean;
        esign_provider: import(".prisma/client").$Enums.esign_provider | null;
        esign_envelope_id: string | null;
        seen_by_client_at: Date | null;
        sent_at: Date | null;
        client_signed_at: Date | null;
        expires_at: Date | null;
        created_at: Date;
        updated_at: Date;
        deleted_at: Date | null;
        previous_version_id: string | null;
        project_id: string;
        created_by: string;
        approved_by_user_id: string | null;
        deleted_by: string | null;
    }>;
    enqueuePdfGeneration(contractId: string, userId: string): Promise<void>;
    sendToSignWell(contractId: string, recipients: Array<{
        email: string;
        name: string;
        role?: 'signer' | 'cc';
    }>, pdfUrl?: string): Promise<import("../opensign/opensign.service").OpenSignDocument>;
    handleSignWellWebhook(event: any): Promise<void>;
}
