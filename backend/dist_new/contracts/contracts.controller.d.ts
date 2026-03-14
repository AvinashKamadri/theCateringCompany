import { Response } from 'express';
import { ContractsService } from './contracts.service';
import { ContractPdfService } from './contract-pdf.service';
import { PrismaService } from '../prisma.service';
export declare class ContractsController {
    private readonly contractsService;
    private readonly contractPdfService;
    private readonly prisma;
    constructor(contractsService: ContractsService, contractPdfService: ContractPdfService, prisma: PrismaService);
    private readonly STAFF_DOMAINS;
    private isStaffEmail;
    findAll(user: {
        userId: string;
        email: string;
    }): Promise<({
        projects_contracts_project_idToprojects: {
            id: string;
            status: import(".prisma/client").$Enums.project_status;
            title: string;
            event_date: Date | null;
            guest_count: number | null;
        };
    } & {
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
    })[]>;
    findOne(id: string, user: {
        userId: string;
    }): Promise<{
        projects_contracts_project_idToprojects: {
            venues: {
                id: string;
                name: string;
                address: string | null;
            } | null;
            id: string;
            status: import(".prisma/client").$Enums.project_status;
            title: string;
            event_date: Date | null;
            guest_count: number | null;
            ai_event_summary: string | null;
        };
    } & {
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
    createContract(projectId: string, userId: string, body: {
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
    generatePdf(id: string, userId: string): Promise<{
        message: string;
    }>;
    servePdf(id: string, res: Response): Promise<void>;
    previewPdf(id: string, user: {
        userId: string;
        email: string;
    }): Promise<{
        pdf_path: string;
    }>;
}
