import { ContractsService } from '../contracts/contracts.service';
export declare class SignWellController {
    private readonly contractsService;
    private readonly logger;
    constructor(contractsService: ContractsService);
    handleWebhook(event: any, signature: string): Promise<{
        success: boolean;
        message: string;
    }>;
    private verifySignature;
}
