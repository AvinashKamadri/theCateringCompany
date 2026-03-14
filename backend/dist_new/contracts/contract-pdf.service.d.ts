import { PrismaService } from '../prisma.service';
export declare class ContractPdfService {
    private readonly prisma;
    private readonly logger;
    constructor(prisma: PrismaService);
    generateSimpleContract(contractId: string): Promise<string>;
}
