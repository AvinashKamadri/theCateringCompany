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
var PricingService_1;
Object.defineProperty(exports, "__esModule", { value: true });
exports.PricingService = void 0;
const common_1 = require("@nestjs/common");
const prisma_service_1 = require("../prisma.service");
const RULES = {
    TAX_RATE: 0.094,
    GRATUITY_RATE: 0.20,
    DEPOSIT_PERCENTAGE: 0.50,
    GUESTS_PER_SERVER: 20,
    GUESTS_PER_BARTENDER: 75,
    MIN_SERVERS: 2,
    MIN_BARTENDERS: 1,
    SERVER_HOURLY_RATE: 25,
    BARTENDER_HOURLY_RATE: 30,
    EVENT_DURATION_HOURS: 6,
    UTENSIL_PER_PERSON: 2.50,
    RENTAL_RATES: { linens: 8, tables: 15, chairs: 5 },
    GUESTS_PER_TABLE: 8,
    PREMIUM_GUEST_THRESHOLD: 75,
};
let PricingService = PricingService_1 = class PricingService {
    constructor(prisma) {
        this.prisma = prisma;
        this.logger = new common_1.Logger(PricingService_1.name);
    }
    calcServiceSurcharge(guestCount, serviceType) {
        if (!serviceType?.toLowerCase().includes('on-site'))
            return 0;
        const servers = Math.max(RULES.MIN_SERVERS, Math.floor(guestCount / RULES.GUESTS_PER_SERVER) + 1);
        const bartenders = Math.max(RULES.MIN_BARTENDERS, Math.floor(guestCount / RULES.GUESTS_PER_BARTENDER));
        return (servers * RULES.EVENT_DURATION_HOURS * RULES.SERVER_HOURLY_RATE +
            bartenders * RULES.EVENT_DURATION_HOURS * RULES.BARTENDER_HOURLY_RATE);
    }
    async calculateEventPricing(input) {
        const { guestCount, eventType, serviceType, menuItems, addons } = input;
        const dbItems = await this.prisma.menu_items.findMany({
            where: { active: true },
            include: { menu_categories: { select: { name: true } } },
        });
        const lineItems = [];
        const seen = new Set();
        const addItem = (item, category) => {
            if (seen.has(item.name))
                return;
            seen.add(item.name);
            const price = Number(item.unit_price ?? 0);
            const isPerPerson = (item.price_type ?? 'per_person') === 'per_person';
            const qty = isPerPerson ? guestCount : 1;
            lineItems.push({
                description: item.name,
                quantity: qty,
                unitPrice: price,
                total: round2(price * qty),
                category,
            });
        };
        for (const name of menuItems) {
            if (!name?.trim())
                continue;
            const lower = name.toLowerCase().trim();
            const catLabel = 'Menu';
            const exact = dbItems.find(i => i.name.toLowerCase() === lower);
            if (exact) {
                addItem(exact, exact.menu_categories?.name ?? catLabel);
                continue;
            }
            const partial = dbItems.filter(i => i.name.toLowerCase().includes(lower) || lower.includes(i.name.toLowerCase()));
            if (partial.length) {
                partial.forEach(i => addItem(i, i.menu_categories?.name ?? catLabel));
                continue;
            }
            const byCat = dbItems.filter(i => (i.menu_categories?.name ?? '').toLowerCase().includes(lower) ||
                lower.includes((i.menu_categories?.name ?? '').toLowerCase()));
            byCat.forEach(i => addItem(i, i.menu_categories?.name ?? catLabel));
        }
        for (const addon of addons) {
            if (!addon?.trim())
                continue;
            const lower = addon.toLowerCase();
            const dbAddon = dbItems.find(i => i.name.toLowerCase().includes(lower.replace(/^.*?:\s*/, '').toLowerCase()) ||
                lower.includes(i.name.toLowerCase()));
            if (dbAddon && !seen.has(dbAddon.name)) {
                addItem(dbAddon, dbAddon.menu_categories?.name ?? 'Add-ons');
                continue;
            }
            if (lower.includes('utensil')) {
                lineItems.push({ description: addon, quantity: guestCount, unitPrice: RULES.UTENSIL_PER_PERSON, total: round2(RULES.UTENSIL_PER_PERSON * guestCount), category: 'Utensils' });
            }
            else if (lower.includes('table')) {
                const qty = Math.max(1, Math.floor(guestCount / RULES.GUESTS_PER_TABLE));
                lineItems.push({ description: 'Table Rental', quantity: qty, unitPrice: RULES.RENTAL_RATES.tables, total: round2(RULES.RENTAL_RATES.tables * qty), category: 'Rentals' });
            }
            else if (lower.includes('chair')) {
                lineItems.push({ description: 'Chair Rental', quantity: guestCount, unitPrice: RULES.RENTAL_RATES.chairs, total: round2(RULES.RENTAL_RATES.chairs * guestCount), category: 'Rentals' });
            }
            else if (lower.includes('linen')) {
                const qty = Math.max(1, Math.floor(guestCount / RULES.GUESTS_PER_TABLE));
                lineItems.push({ description: 'Linen Rental', quantity: qty, unitPrice: RULES.RENTAL_RATES.linens, total: round2(RULES.RENTAL_RATES.linens * qty), category: 'Rentals' });
            }
        }
        const packages = await this.prisma.pricing_packages.findMany({
            where: { active: true },
            orderBy: { priority: 'asc' },
        });
        const eventLower = eventType.toLowerCase();
        const candidates = packages.filter(p => {
            const cat = (p.category ?? '').toLowerCase();
            const name = (p.name ?? '').toLowerCase();
            if (eventLower.includes('wedding'))
                return cat.includes('wedding') || name.includes('wedding');
            if (eventLower.includes('corporate'))
                return cat.includes('premium') || cat.includes('corporate');
            return cat.includes('standard');
        });
        const pool = candidates.length ? candidates : packages;
        const selectedPackage = pool.length
            ? pool.reduce((best, p) => {
                const pPrice = Number(p.base_price ?? 0);
                const bPrice = Number(best?.base_price ?? 0);
                return guestCount > RULES.PREMIUM_GUEST_THRESHOLD
                    ? (pPrice > bPrice ? p : best)
                    : (pPrice < bPrice ? p : best);
            }, pool[0])
            : null;
        const packageRate = selectedPackage ? Number(selectedPackage.base_price ?? 0) : 0;
        const packageBase = round2(packageRate * guestCount);
        const hasMatchedFoodItems = lineItems.some(li => li.category === 'Menu');
        if (!hasMatchedFoodItems && selectedPackage && packageBase > 0) {
            const ppRate = Number(selectedPackage.base_price ?? 0);
            lineItems.unshift({
                description: `${selectedPackage.name} (${guestCount} guests × $${ppRate}/pp)`,
                quantity: guestCount,
                unitPrice: ppRate,
                total: packageBase,
                category: 'Package',
            });
        }
        const foodSubtotal = round2(lineItems.reduce((s, i) => s + i.total, 0));
        const menuTotal = round2(Math.max(foodSubtotal, packageBase));
        const serviceSurcharge = round2(this.calcServiceSurcharge(guestCount, serviceType));
        const subtotalBeforeFees = round2(menuTotal + serviceSurcharge);
        const tax = round2(subtotalBeforeFees * RULES.TAX_RATE);
        const gratuity = round2(subtotalBeforeFees * RULES.GRATUITY_RATE);
        const grandTotal = round2(subtotalBeforeFees + tax + gratuity);
        const deposit = round2(grandTotal * RULES.DEPOSIT_PERCENTAGE);
        this.logger.log(`💰 Pricing for ${guestCount} guests (${eventType}, ${serviceType}): $${grandTotal} total`);
        return {
            lineItems,
            packageName: selectedPackage?.name ?? null,
            packagePerPersonRate: packageRate || null,
            foodSubtotal,
            packageBase,
            menuTotal,
            serviceSurcharge,
            subtotalBeforeFees,
            tax,
            taxRate: RULES.TAX_RATE,
            gratuity,
            gratuityRate: RULES.GRATUITY_RATE,
            grandTotal,
            deposit,
            balance: round2(grandTotal - deposit),
        };
    }
};
exports.PricingService = PricingService;
exports.PricingService = PricingService = PricingService_1 = __decorate([
    (0, common_1.Injectable)(),
    __metadata("design:paramtypes", [prisma_service_1.PrismaService])
], PricingService);
function round2(n) {
    return Math.round(n * 100) / 100;
}
//# sourceMappingURL=pricing.service.js.map