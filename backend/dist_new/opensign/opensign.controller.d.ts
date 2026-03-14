import { OpenSignService } from './opensign.service';
export declare class OpenSignController {
    private readonly openSignService;
    private readonly logger;
    constructor(openSignService: OpenSignService);
    handleWebhook(body: any, signature?: string): Promise<{
        success: boolean;
        message: string;
    }>;
}
