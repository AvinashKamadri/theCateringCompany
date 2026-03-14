import { Injectable, Logger } from '@nestjs/common';
import { PrismaService } from '../prisma.service';

// ─── Business Rules ────────────────────────────────────────────────────────────
// Mirrors config/business_rules.py from the ML agent — single source of truth
// for all financial constants. Update here, not in the frontend.
const RULES = {
  TAX_RATE: 0.094,          // 9.4%
  GRATUITY_RATE: 0.20,      // 20%
  DEPOSIT_PERCENTAGE: 0.50, // 50%
  // On-site staffing
  GUESTS_PER_SERVER: 20,
  GUESTS_PER_BARTENDER: 75,
  MIN_SERVERS: 2,
  MIN_BARTENDERS: 1,
  SERVER_HOURLY_RATE: 25,
  BARTENDER_HOURLY_RATE: 30,
  EVENT_DURATION_HOURS: 6,
  // Fallback add-on rates (used when item not found in DB)
  UTENSIL_PER_PERSON: 2.50,
  RENTAL_RATES: { linens: 8, tables: 15, chairs: 5 },
  GUESTS_PER_TABLE: 8,
  // Package selection threshold
  PREMIUM_GUEST_THRESHOLD: 75,
} as const;

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
  menuItems: string[];   // dish names from contract body
  addons: string[];      // addon strings like "Utensils: Premium set"
}

@Injectable()
export class PricingService {
  private readonly logger = new Logger(PricingService.name);

  constructor(private readonly prisma: PrismaService) {}

  // ─── Service Surcharge (labor for on-site events) ───────────────────────────
  private calcServiceSurcharge(guestCount: number, serviceType: string): number {
    if (!serviceType?.toLowerCase().includes('on-site')) return 0;
    const servers = Math.max(RULES.MIN_SERVERS, Math.floor(guestCount / RULES.GUESTS_PER_SERVER) + 1);
    const bartenders = Math.max(RULES.MIN_BARTENDERS, Math.floor(guestCount / RULES.GUESTS_PER_BARTENDER));
    return (
      servers * RULES.EVENT_DURATION_HOURS * RULES.SERVER_HOURLY_RATE +
      bartenders * RULES.EVENT_DURATION_HOURS * RULES.BARTENDER_HOURLY_RATE
    );
  }

  // ─── Main calculation ────────────────────────────────────────────────────────
  async calculateEventPricing(input: PricingInput): Promise<PricingBreakdown> {
    const { guestCount, eventType, serviceType, menuItems, addons } = input;

    // Load all active menu items + their category names
    const dbItems = await this.prisma.menu_items.findMany({
      where: { active: true },
      include: { menu_categories: { select: { name: true } } },
    });

    const lineItems: LineItem[] = [];
    const seen = new Set<string>();

    const addItem = (item: typeof dbItems[0], category: string) => {
      if (seen.has(item.name)) return;
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

    // Match each menu item name against DB (3 layers: exact → partial → category)
    for (const name of menuItems) {
      if (!name?.trim()) continue;
      const lower = name.toLowerCase().trim();
      const catLabel = 'Menu';

      // 1. Exact name
      const exact = dbItems.find(i => i.name.toLowerCase() === lower);
      if (exact) { addItem(exact, exact.menu_categories?.name ?? catLabel); continue; }

      // 2. Partial name (both directions)
      const partial = dbItems.filter(i =>
        i.name.toLowerCase().includes(lower) || lower.includes(i.name.toLowerCase()),
      );
      if (partial.length) { partial.forEach(i => addItem(i, i.menu_categories?.name ?? catLabel)); continue; }

      // 3. Category name match
      const byCat = dbItems.filter(i =>
        (i.menu_categories?.name ?? '').toLowerCase().includes(lower) ||
        lower.includes((i.menu_categories?.name ?? '').toLowerCase()),
      );
      byCat.forEach(i => addItem(i, i.menu_categories?.name ?? catLabel));
    }

    // Add-on line items (utensils, rentals, desserts, florals)
    for (const addon of addons) {
      if (!addon?.trim()) continue;
      const lower = addon.toLowerCase();

      // First: try to find it in the DB
      const dbAddon = dbItems.find(i =>
        i.name.toLowerCase().includes(lower.replace(/^.*?:\s*/, '').toLowerCase()) ||
        lower.includes(i.name.toLowerCase()),
      );
      if (dbAddon && !seen.has(dbAddon.name)) {
        addItem(dbAddon, dbAddon.menu_categories?.name ?? 'Add-ons');
        continue;
      }

      // Fallback: use hardcoded rates
      if (lower.includes('utensil')) {
        lineItems.push({ description: addon, quantity: guestCount, unitPrice: RULES.UTENSIL_PER_PERSON, total: round2(RULES.UTENSIL_PER_PERSON * guestCount), category: 'Utensils' });
      } else if (lower.includes('table')) {
        const qty = Math.max(1, Math.floor(guestCount / RULES.GUESTS_PER_TABLE));
        lineItems.push({ description: 'Table Rental', quantity: qty, unitPrice: RULES.RENTAL_RATES.tables, total: round2(RULES.RENTAL_RATES.tables * qty), category: 'Rentals' });
      } else if (lower.includes('chair')) {
        lineItems.push({ description: 'Chair Rental', quantity: guestCount, unitPrice: RULES.RENTAL_RATES.chairs, total: round2(RULES.RENTAL_RATES.chairs * guestCount), category: 'Rentals' });
      } else if (lower.includes('linen')) {
        const qty = Math.max(1, Math.floor(guestCount / RULES.GUESTS_PER_TABLE));
        lineItems.push({ description: 'Linen Rental', quantity: qty, unitPrice: RULES.RENTAL_RATES.linens, total: round2(RULES.RENTAL_RATES.linens * qty), category: 'Rentals' });
      }
    }

    // Select pricing package from DB
    const packages = await this.prisma.pricing_packages.findMany({
      where: { active: true },
      orderBy: { priority: 'asc' },
    });

    const eventLower = eventType.toLowerCase();
    const candidates = packages.filter(p => {
      const cat = (p.category ?? '').toLowerCase();
      const name = (p.name ?? '').toLowerCase();
      if (eventLower.includes('wedding')) return cat.includes('wedding') || name.includes('wedding');
      if (eventLower.includes('corporate')) return cat.includes('premium') || cat.includes('corporate');
      return cat.includes('standard');
    });

    const pool = candidates.length ? candidates : packages;
    // Larger events → higher tier package
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

    // If no food items matched the DB, add the selected package as a base food line item
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

    // Use the HIGHER of per-item subtotal vs package base (industry standard)
    const foodSubtotal = round2(lineItems.reduce((s, i) => s + i.total, 0));
    const menuTotal = round2(Math.max(foodSubtotal, packageBase));

    const serviceSurcharge = round2(this.calcServiceSurcharge(guestCount, serviceType));
    const subtotalBeforeFees = round2(menuTotal + serviceSurcharge);
    const tax = round2(subtotalBeforeFees * RULES.TAX_RATE);
    const gratuity = round2(subtotalBeforeFees * RULES.GRATUITY_RATE);
    const grandTotal = round2(subtotalBeforeFees + tax + gratuity);
    const deposit = round2(grandTotal * RULES.DEPOSIT_PERCENTAGE);

    this.logger.log(
      `💰 Pricing for ${guestCount} guests (${eventType}, ${serviceType}): $${grandTotal} total`,
    );

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
}

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}
