import { ContractsService } from './contracts.service';
import { ContractPdfService } from './contract-pdf.service';
import { PrismaService } from '../prisma.service';
import { PricingService } from '../pricing/pricing.service';
export declare class StaffContractsController {
    private readonly contractsService;
    private readonly contractPdfService;
    private readonly prisma;
    private readonly pricingService;
    private readonly logger;
    constructor(contractsService: ContractsService, contractPdfService: ContractPdfService, prisma: PrismaService, pricingService: PricingService);
    getAllContracts(user: {
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
        previous_version_id: string | null;
        project_id: string;
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
        created_by: string;
        approved_by_user_id: string | null;
        seen_by_client_at: Date | null;
        sent_at: Date | null;
        client_signed_at: Date | null;
        expires_at: Date | null;
        created_at: Date;
        updated_at: Date;
        deleted_at: Date | null;
        deleted_by: string | null;
    })[]>;
    getPendingContracts(user: {
        userId: string;
        email: string;
    }): Promise<{
        contracts: ({
            users_contracts_created_byTousers: {
                id: string;
                email: string;
            };
            projects_contracts_project_idToprojects: {
                id: string;
                title: string;
                event_date: Date | null;
                guest_count: number | null;
                ai_event_summary: string | null;
            };
        } & {
            id: string;
            contract_group_id: string;
            version_number: number;
            previous_version_id: string | null;
            project_id: string;
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
            created_by: string;
            approved_by_user_id: string | null;
            seen_by_client_at: Date | null;
            sent_at: Date | null;
            client_signed_at: Date | null;
            expires_at: Date | null;
            created_at: Date;
            updated_at: Date;
            deleted_at: Date | null;
            deleted_by: string | null;
        })[];
        count: number;
    }>;
    getContractForReview(contractId: string, user: {
        userId: string;
        email: string;
    }): Promise<{
        users_contracts_created_byTousers: {
            id: string;
            email: string;
            primary_phone: string | null;
        };
        projects_contracts_project_idToprojects: {
            id: string;
            title: string;
            event_date: Date | null;
            event_end_date: Date | null;
            guest_count: number | null;
            ai_event_summary: string | null;
            venues: {
                name: string;
                address: string | null;
            } | null;
        };
    } & {
        id: string;
        contract_group_id: string;
        version_number: number;
        previous_version_id: string | null;
        project_id: string;
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
        created_by: string;
        approved_by_user_id: string | null;
        seen_by_client_at: Date | null;
        sent_at: Date | null;
        client_signed_at: Date | null;
        expires_at: Date | null;
        created_at: Date;
        updated_at: Date;
        deleted_at: Date | null;
        deleted_by: string | null;
    }>;
    approveContract(contractId: string, user: {
        userId: string;
        email: string;
    }, body: {
        message?: string;
        adjustments?: any;
    }): Promise<{
        success: boolean;
        message: string;
        opensign_document_id: string;
        signing_url: string | undefined;
    }>;
    rejectContract(contractId: string, user: {
        userId: string;
        email: string;
    }, body: {
        reason: string;
    }): Promise<{
        success: boolean;
        message: string;
    }>;
    calculatePricing(contractId: string, user: {
        userId: string;
        email: string;
    }): Promise<import("../pricing/pricing.service").PricingBreakdown>;
    updatePricing(contractId: string, user: {
        userId: string;
        email: string;
    }, body: {
        pricing: any;
    }): Promise<{
        success: boolean;
        message: string;
    }>;
}
