import { PrismaService } from '../prisma.service';
export interface LineItem {
    description: string;
    quantity: number;
    unitPrice: number;
    total: number;
    category: string;
}
export interface PricingBreakdown {
    lineItems: LineItem[];
    packageName: string | null;
    packagePerPersonRate: number | null;
    foodSubtotal: number;
    packageBase: number;
    menuTotal: number;
    serviceSurcharge: number;
    subtotalBeforeFees: number;
    tax: number;
    taxRate: number;
    gratuity: number;
    gratuityRate: number;
    grandTotal: number;
    deposit: number;
    balance: number;
}
export interface PricingInput {
    guestCount: number;
    eventType: string;
    serviceType: string;
    menuItems: string[];
    addons: string[];
}
export declare class PricingService {
    private readonly prisma;
    private readonly logger;
    constructor(prisma: PrismaService);
    private calcServiceSurcharge;
    calculateEventPricing(input: PricingInput): Promise<PricingBreakdown>;
}
