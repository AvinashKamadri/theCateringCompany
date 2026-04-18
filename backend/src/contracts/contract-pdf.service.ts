import { Injectable, Logger } from '@nestjs/common';
import { PrismaService } from '../prisma.service';
import * as fs from 'fs/promises';
import * as path from 'path';

@Injectable()
export class ContractPdfService {
  private readonly logger = new Logger(ContractPdfService.name);

  constructor(private readonly prisma: PrismaService) {}

  async generateSimpleContract(contractId: string): Promise<string> {
    this.logger.log(`📄 Generating PDF contract for ${contractId}`);

    const contract = await this.prisma.contracts.findUnique({
      where: { id: contractId },
      include: {
        projects_contracts_project_idToprojects: {
          select: {
            title: true,
            event_date: true,
            event_end_date: true,
            guest_count: true,
            venues: { select: { name: true, address: true } },
          },
        },
        users_contracts_created_byTousers: {
          select: { email: true, primary_phone: true },
        },
      },
    });

    if (!contract) throw new Error('Contract not found');

    const body = contract.body as any || {};
    const project = contract.projects_contracts_project_idToprojects;
    const creatorEmail = contract.users_contracts_created_byTousers?.email || '';

    // Support both body shapes: {client_info, event_details, menu} and {slots}
    const slots = body.slots || {};
    const clientInfo = body.client_info || {};
    const eventDetails = body.event_details || {};
    const menuData = body.menu || {};
    const additional = body.additional || {};

    const clientName = clientInfo.name || slots.name || project?.title || '';
    const clientEmail = clientInfo.email || slots.email || creatorEmail;
    const clientPhone = clientInfo.phone || slots.phone || contract.users_contracts_created_byTousers?.primary_phone || '';
    const eventType = eventDetails.type || slots.event_type || '';
    const eventDate = eventDetails.date || slots.event_date
      || (project?.event_date ? new Date(project.event_date).toLocaleDateString('en-US', { month: 'numeric', day: 'numeric', year: 'numeric' }) : '');
    const guestCount = eventDetails.guest_count || slots.guest_count || project?.guest_count || '';
    const serviceType = eventDetails.service_type || slots.service_type || '';
    const venueName = eventDetails.venue?.name || slots.venue || project?.venues?.name || '';
    const venueAddress = eventDetails.venue?.address || project?.venues?.address || '';
    const parseCommaSep = (v: any): string[] => {
      if (!v || v === 'none' || v === 'no') return [];
      if (Array.isArray(v)) return v.filter(Boolean);
      return String(v).split(',').map((s: string) => s.trim()).filter(Boolean);
    };
    const appetizers: string[] = menuData.appetizers?.length
      ? menuData.appetizers.map((i: any) => (typeof i === 'string' ? i : i.name || i)).filter(Boolean)
      : parseCommaSep(slots.appetizers);
    const mainDishes: string[] = menuData.main_dishes?.length
      ? menuData.main_dishes.map((i: any) => (typeof i === 'string' ? i : i.name || i)).filter(Boolean)
      : (menuData.items?.length
          ? menuData.items.map((i: any) => (typeof i === 'string' ? i : i.name || i)).filter(Boolean)
          : parseCommaSep(slots.selected_dishes));
    const desserts: string[] = menuData.desserts?.length
      ? menuData.desserts.map((i: any) => (typeof i === 'string' ? i : i.name || i)).filter(Boolean)
      : parseCommaSep(slots.desserts);
    const utensils: string = (slots.utensils && slots.utensils !== 'no') ? String(slots.utensils) : '';
    const rentals: string = (slots.rentals && slots.rentals !== 'no') ? String(slots.rentals) : '';
    const florals: string = (slots.florals && slots.florals !== 'no') ? String(slots.florals) : '';
    const dietaryRestrictions: string[] = menuData.dietary_restrictions || (slots.dietary_concerns ? [slots.dietary_concerns] : []);
    const addons: string[] = additional.addons || [];
    const modifications: string[] = additional.modifications || [];
    const pricing = body.pricing || {};
    const lineItems: Array<{ description: string; quantity: number; unitPrice: number }> =
      Array.isArray(pricing.lineItems) ? pricing.lineItems : [];
    const lineSubtotal = lineItems.reduce((s, i) => s + i.quantity * i.unitPrice, 0);
    // subtotal = pre-fee sum of line items; total_amount = grand total (includes tax + gratuity)
    // Use pricing.subtotal if present (saved by new flow), else compute from line items
    const subtotal = pricing.subtotal > 0 ? pricing.subtotal : (lineItems.length > 0 ? lineSubtotal : 0);
    const tax = subtotal > 0 ? subtotal * 0.094 : 0;
    const gratuity = subtotal > 0 ? subtotal * 0.20 : 0;
    // Grand total: prefer stored total_amount (authoritative), else compute
    const grandTotal = contract.total_amount ? Number(contract.total_amount)
      : (subtotal > 0 ? subtotal + tax + gratuity : 0);
    const totalAmount = grandTotal > 0 ? `$${Math.round(grandTotal).toLocaleString()}` : 'TBD';
    const contractSummary = body.contract_text || body.summary || '';

    const depositAmount = grandTotal > 0 ? `$${Math.round(grandTotal / 2).toLocaleString()}` : 'TBD';

    const html = buildContractHtml({
      contractId,
      clientName,
      clientEmail,
      clientPhone,
      eventType,
      eventDate,
      guestCount: String(guestCount),
      serviceType,
      venueName,
      venueAddress,
      appetizers,
      mainDishes,
      desserts,
      utensils,
      rentals,
      florals,
      dietaryRestrictions,
      addons,
      modifications,
      lineItems,
      tax: Math.round(tax),
      gratuity: Math.round(gratuity),
      deposit: depositAmount,
      totalAmount,
      contractSummary,
      createdAt: new Date(contract.created_at).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' }),
    });

    // Generate PDF via puppeteer
    const uploadsDir = path.join(process.cwd(), 'uploads', 'contracts');
    await fs.mkdir(uploadsDir, { recursive: true });

    const filename = `contract-${contractId}-${Date.now()}.pdf`;
    const filePath = path.join(uploadsDir, filename);

    let pdfBuffer: Buffer;
    try {
      const puppeteer = await import('puppeteer');
      const browser = await puppeteer.default.launch({
        headless: true,
        executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || undefined,
        args: ['--no-sandbox', '--disable-setuid-sandbox'],
      });
      const page = await browser.newPage();
      await page.setContent(html, { waitUntil: 'networkidle0' });
      pdfBuffer = Buffer.from(await page.pdf({
        format: 'Letter',
        printBackground: true,
        displayHeaderFooter: true,
        headerTemplate: `<div style="-webkit-print-color-adjust:exact;print-color-adjust:exact;width:100%;background:#1A1A2E;padding:12px 22px;display:flex;justify-content:space-between;align-items:center;font-family:Arial,Helvetica,sans-serif;font-size:10px;border-bottom:2.5px solid #C9A84C;box-sizing:border-box;position:relative;"><div style="position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,#C9A84C,#E8C97A,#C9A84C);"></div><div><div style="font-family:Georgia,serif;font-size:20px;font-weight:700;color:#fff;line-height:1.15;">The Catering <span style="color:#C9A84C;">Company</span></div><div style="color:#E8C97A;font-style:italic;font-size:9px;margin-top:3px;letter-spacing:0.8px;">Catering Service Agreement</div></div><div style="width:1px;align-self:stretch;background:linear-gradient(to bottom,transparent,#C9A84C,transparent);margin:2px 18px;flex-shrink:0;"></div><div style="text-align:right;color:rgba(255,255,255,0.75);font-size:8.5px;line-height:1.8;">info@thecatering-company.com &nbsp;|&nbsp; 540-868-8410<br/>1930 Front Royal Pike, Winchester VA 22602</div></div>`,
        footerTemplate: `<div style="-webkit-print-color-adjust:exact;print-color-adjust:exact;width:100%;background:#1A1A2E;padding:5px 22px;display:flex;justify-content:space-between;align-items:center;font-family:Arial,Helvetica,sans-serif;font-size:8.5px;color:rgba(255,255,255,0.72);border-top:2px solid #C9A84C;box-sizing:border-box;"><span>The Catering Company &nbsp;·&nbsp; info@thecatering-company.com &nbsp;·&nbsp; 540-868-8410 &nbsp;·&nbsp; 1930 Front Royal Pike, Winchester VA 22602</span><span style="white-space:nowrap;margin-left:12px;">Page <span class="pageNumber"></span> of <span class="totalPages"></span></span></div>`,
        margin: { top: '1.2in', bottom: '0.45in', left: '0.65in', right: '0.65in' },
      }));
      await browser.close();
    } catch (err: any) {
      this.logger.error('Puppeteer PDF generation failed, falling back to text', err.message);
      // Fallback: save HTML as text for debugging
      await fs.writeFile(filePath.replace('.pdf', '.html'), html, 'utf-8');
      throw new Error(`PDF generation failed: ${err.message}`);
    }

    await fs.writeFile(filePath, pdfBuffer);
    this.logger.log(`✅ PDF saved to ${filePath}`);

    const relativePath = `uploads/contracts/${filename}`;
    await this.prisma.contracts.update({
      where: { id: contractId },
      data: { pdf_path: relativePath },
    });

    return relativePath;
  }
}

// ─── HTML Template ────────────────────────────────────────────────────────────

interface LineItem {
  description: string;
  quantity: number;
  unitPrice: number;
}

interface TemplateData {
  contractId: string;
  clientName: string;
  clientEmail: string;
  clientPhone: string;
  eventType: string;
  eventDate: string;
  guestCount: string;
  serviceType: string;
  venueName: string;
  venueAddress: string;
  appetizers: string[];
  mainDishes: string[];
  desserts: string[];
  utensils: string;
  rentals: string;
  florals: string;
  dietaryRestrictions: string[];
  addons: string[];
  modifications: string[];
  lineItems: LineItem[];
  tax: number;
  gratuity: number;
  deposit: string;
  totalAmount: string;
  contractSummary: string;
  createdAt: string;
}

function buildContractHtml(d: TemplateData): string {
  const flourish = `
    <div style="display:flex;align-items:center;margin:14px 0;">
      <div style="flex:1;height:1px;background:linear-gradient(to right,transparent,#C9A84C);position:relative;">
        <div style="position:absolute;top:-2.5px;left:0;right:0;height:0.5px;background:linear-gradient(to right,transparent,#C9A84C);opacity:0.4;"></div>
      </div>
      <div style="padding:0 12px;display:flex;align-items:center;gap:5px;color:#C9A84C;">
        <span style="width:3px;height:3px;background:#C9A84C;border-radius:50%;display:inline-block;"></span>
        <span style="width:3px;height:3px;background:#C9A84C;border-radius:50%;display:inline-block;"></span>
        <span style="width:5px;height:5px;background:#C9A84C;transform:rotate(45deg);display:inline-block;opacity:0.6;"></span>
        <svg width="28" height="18" viewBox="0 0 28 18" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M14 9 C12 16 4 18 2 12 C0 6 6 2 12 6 C13 7 14 9 14 9 Z" stroke="#C9A84C" stroke-width="1.2" fill="none"/>
          <path d="M14 9 C16 16 24 18 26 12 C28 6 22 2 16 6 C15 7 14 9 14 9 Z" stroke="#C9A84C" stroke-width="1.2" fill="none"/>
          <rect x="12.5" y="7.5" width="3" height="3" transform="rotate(45 14 9)" fill="#C9A84C"/>
        </svg>
        <span style="width:5px;height:5px;background:#C9A84C;transform:rotate(45deg);display:inline-block;opacity:0.6;"></span>
        <span style="width:3px;height:3px;background:#C9A84C;border-radius:50%;display:inline-block;"></span>
        <span style="width:3px;height:3px;background:#C9A84C;border-radius:50%;display:inline-block;"></span>
      </div>
      <div style="flex:1;height:1px;background:linear-gradient(to left,transparent,#C9A84C);position:relative;">
        <div style="position:absolute;top:-2.5px;left:0;right:0;height:0.5px;background:linear-gradient(to left,transparent,#C9A84C);opacity:0.4;"></div>
      </div>
    </div>`;

  const sectionBanner = (title: string, right = '') => `
    <div style="
      background:#1A1A2E;color:#fff;
      font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:2px;
      padding:7px 14px 7px 18px;margin-top:18px;margin-bottom:0;
      position:relative;display:flex;justify-content:space-between;align-items:center;
      border-left:4px solid #E8C97A;
      border-right:3px solid #C9A84C;
      border-bottom:2px solid #C9A84C;
    ">
      <span>${title}</span>
      ${right ? `<span style="font-size:9px;font-weight:400;opacity:0.8;">${right}</span>` : `
      <span style="display:flex;gap:4px;align-items:center;">
        <i style="width:4px;height:4px;background:#C9A84C;transform:rotate(45deg);display:inline-block;opacity:0.7;font-style:normal;"></i>
        <i style="width:4px;height:4px;background:#C9A84C;transform:rotate(45deg);display:inline-block;opacity:0.7;font-style:normal;"></i>
        <i style="width:4px;height:4px;background:#C9A84C;transform:rotate(45deg);display:inline-block;opacity:0.7;font-style:normal;"></i>
      </span>`}
    </div>`;

  const infoRow = (label: string, value: string, alt = false) => value ? `
    <div style="display:flex;align-items:stretch;border-bottom:1px solid #E8E0D0;${alt ? 'background:#F5F0E8;' : 'background:#FDF8F0;'}">
      <div style="width:38%;font-weight:700;font-size:9px;color:#4A4A6A;text-transform:uppercase;letter-spacing:0.5px;
        padding:6px 8px;border-right:1px solid #E8E0D0;border-left:3px solid #C9A84C;display:flex;align-items:center;">
        ${label}
      </div>
      <div style="padding:6px 10px;font-size:10.5px;flex:1;display:flex;align-items:center;color:#1A1A2E;">
        ${value}
      </div>
    </div>` : '';

  const menuRow = (name: string, price = '', alt = false) => `
    <div style="display:flex;justify-content:space-between;align-items:center;
      padding:4px 12px 4px 14px;font-size:10.5px;border-bottom:1px solid #E8E0D0;
      ${alt ? 'background:#F5F0E8;' : 'background:#FDF8F0;'}
      border-left:3px solid #C9A84C;">
      <span><span style="color:#C9A84C;font-size:7px;vertical-align:middle;">◆</span>&nbsp;&nbsp;${name}</span>
      ${price ? `<span style="color:#C9A84C;font-weight:700;font-size:10px;">${price}</span>` : ''}
    </div>`;

  const billRow = (label: string, value: string, alt = false, muted = false) => `
    <div style="display:flex;justify-content:space-between;align-items:center;
      padding:5px 14px;border-bottom:1px solid #E8E0D0;font-size:10.5px;
      ${alt ? 'background:#F5F0E8;' : 'background:#FDF8F0;'}
      ${muted ? 'font-style:italic;color:#4A4A6A;font-size:10px;' : ''}">
      <span>${label}</span><span>${value}</span>
    </div>`;

  const buildMenuSection = (title: string, items: string[]) => {
    if (!items.length) return '';
    return `
      <div style="font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;
        color:#C9A84C;padding:6px 10px 5px 14px;border-bottom:1px solid rgba(201,168,76,.2);
        background:#fff;border-left:3px solid #C9A84C;border-top:1px solid #E8E0D0;">
        ${title}
      </div>
      ${items.map((item, i) => menuRow(item, '', i % 2 !== 0)).join('')}`;
  };

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: Arial, Helvetica, sans-serif;
    font-size: 12px;
    color: #1A1A2E;
    line-height: 1.55;
    background: transparent;
  }
  @page { background: #FDFAF5; size: Letter; }

  .page-break { page-break-before: always; padding-top: 8px; }

  .terms { font-size: 10px; color: #333; line-height: 1.6; padding: 10px 14px;
    border: 1px solid #E8E0D0; border-top: none; }
  .terms h4 { font-size: 9px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.8px; color: #C9A84C; margin: 8px 0 2px; }
  .terms h4:first-child { margin-top: 0; }
  .terms p { margin-bottom: 4px; font-size: 9.5px; color: #4A4A6A; }
  .terms .tfn { text-align:center;margin-top:10px;padding-top:7px;
    border-top:1px solid #E8E0D0;font-size:9.5px;color:#4A4A6A; }

  .sig-intro { font-size: 12px; font-style: italic; color: #4A4A6A;
    padding: 10px 14px 8px; text-align: center;
    border-left: 1px solid #E8E0D0; border-right: 1px solid #E8E0D0; }
  .sig-grid { display: grid; grid-template-columns: 1fr 1fr;
    border: 1px solid #E8E0D0; border-top: none; }
  .sig-col { padding: 14px 16px 18px; }
  .sig-col + .sig-col { border-left: 1px solid #E8E0D0; background: rgba(245,240,232,.4); }
  .sig-label { font-size: 8px; font-weight: 700; color: #4A4A6A;
    text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 5px; display: block; }
  .sig-line { border-bottom: 1.5px solid #C9A84C; height: 26px; margin-bottom: 14px; }
  .sig-name-line { border-bottom: 1px solid rgba(201,168,76,.4); height: 22px; margin-bottom: 14px; }
  .sig-inline { display: flex; gap: 14px; align-items: flex-end; }
  .sig-inline .sp { flex: 2; }
  .sig-inline .sp.date { flex: 1; }
</style>
</head>
<body>

<!-- ═══ EVENT & CLIENT INFORMATION ═══ -->
${sectionBanner('Event &amp; Client Information')}
<div style="display:grid;grid-template-columns:1fr 1fr;border:1px solid #E8E0D0;border-top:none;">
  <div style="border-right:1px solid #E8E0D0;">
    ${infoRow('Client Name', d.clientName, false)}
    ${infoRow('Email',       d.clientEmail, true)}
    ${infoRow('Phone',       d.clientPhone, false)}
    ${infoRow('Contract Date', d.createdAt, true)}
  </div>
  <div>
    ${infoRow('Event Date',    d.eventDate, false)}
    ${infoRow('Event Type',    d.eventType, true)}
    ${infoRow('Guest Count',   d.guestCount ? `${d.guestCount} guests (Guarantee: ${Math.ceil(Number(d.guestCount) * 0.9)} at 90%)` : '', false)}
    ${infoRow('Service Style', d.serviceType, true)}
  </div>
</div>
${d.venueName ? `
<div style="display:flex;border:1px solid #E8E0D0;border-top:none;background:#F5F0E8;">
  <div style="width:19%;font-weight:700;font-size:9px;color:#4A4A6A;text-transform:uppercase;
    letter-spacing:0.5px;padding:6px 8px;border-right:1px solid #E8E0D0;
    border-left:3px solid #C9A84C;display:flex;align-items:center;">Venue</div>
  <div style="padding:6px 10px;font-size:10.5px;flex:1;color:#1A1A2E;">
    ${d.venueName}${d.venueAddress ? ', ' + d.venueAddress : ''}
  </div>
</div>` : ''}

${flourish}

<!-- ═══ MENU & SERVICES ═══ -->
${(d.appetizers.length > 0 || d.mainDishes.length > 0 || d.desserts.length > 0) ? `
${sectionBanner('Menu &amp; Services')}
<div style="border:1px solid #E8E0D0;border-top:none;">
  ${buildMenuSection("Appetizers / Hors d'Oeuvres", d.appetizers)}
  ${buildMenuSection('Main Dishes', d.mainDishes)}
  ${buildMenuSection('Desserts', d.desserts)}
  ${(d.utensils || d.rentals || d.florals) ? `
  <div style="padding:6px 10px 6px 14px;border-top:1px solid #E8E0D0;font-size:10px;color:#4A4A6A;">
    ${d.utensils ? `<span><strong>Utensils:</strong> ${d.utensils}</span>&nbsp;&nbsp;` : ''}
    ${d.rentals  ? `<span><strong>Rentals:</strong> ${d.rentals}</span>&nbsp;&nbsp;` : ''}
    ${d.florals  ? `<span><strong>Florals:</strong> ${d.florals}</span>` : ''}
  </div>` : ''}
  ${d.dietaryRestrictions.length > 0 ? `
  <div style="font-size:10px;font-style:italic;color:#4A4A6A;padding:7px 10px 6px 14px;border-top:1px solid #E8E0D0;">
    <strong style="color:#1A1A2E;font-style:normal;">Dietary Restrictions / Allergies:</strong>
    ${d.dietaryRestrictions.join(', ')}
  </div>` : ''}
</div>` : ''}

${(d.addons.length > 0 || d.modifications.length > 0) ? `
${flourish}
${sectionBanner('Add-ons &amp; Special Requests')}
<div style="border:1px solid #E8E0D0;border-top:none;padding:8px 14px;font-size:10.5px;color:#1A1A2E;">
  ${d.addons.length > 0 ? `<div><strong>Add-ons:</strong></div><ul style="padding-left:18px;margin:4px 0;">${d.addons.map(a=>`<li style="margin-bottom:3px;">${a}</li>`).join('')}</ul>` : ''}
  ${d.modifications.length > 0 ? `<div style="margin-top:6px;"><strong>Special Requests:</strong></div><ul style="padding-left:18px;margin:4px 0;">${d.modifications.map(m=>`<li style="margin-bottom:3px;">${m}</li>`).join('')}</ul>` : ''}
</div>` : ''}

${d.contractSummary ? `
${flourish}
${sectionBanner('Service Notes')}
<div style="border:1px solid #E8E0D0;border-top:none;padding:8px 14px;font-size:11px;
  white-space:pre-wrap;line-height:1.6;color:#1A1A2E;">${d.contractSummary}</div>` : ''}

${flourish}

<!-- ═══ BILLING SUMMARY ═══ -->
<div style="page-break-inside:avoid;">
${sectionBanner('Billing Summary')}
<div style="border:1px solid #E8E0D0;border-top:none;margin-bottom:6px;">
  ${d.lineItems.map((item, i) => billRow(
    `${item.description}${item.quantity > 1 ? ` × ${item.quantity}` : ''}`,
    `$${(item.quantity * item.unitPrice).toLocaleString()}`,
    i % 2 !== 0
  )).join('')}
  ${d.lineItems.length > 0 ? `<div style="height:6px;background:#EAE4D4;border-bottom:1px solid #E8E0D0;"></div>` : ''}
  ${d.tax > 0 ? billRow('Tax (9.4%)', `$${d.tax.toLocaleString()}`, false, true) : ''}
  ${d.gratuity > 0 ? billRow('Service &amp; Gratuity (20%)', `$${d.gratuity.toLocaleString()}`, true, true) : ''}
  <div style="height:6px;background:#EAE4D4;border-bottom:1px solid #E8E0D0;"></div>
  <div style="display:flex;justify-content:space-between;align-items:center;
    padding:6px 14px;font-weight:700;font-size:11.5px;
    background:#EAE4D4;border-top:1px solid #D4AF6A;border-bottom:1px solid #D4AF6A;">
    <span>Deposit Due at Signing (50%)</span><span>${d.deposit}</span>
  </div>
  <div style="display:flex;justify-content:space-between;align-items:center;
    padding:9px 14px;
    background:#1A1A2E;color:#fff;
    font-family:Georgia,serif;font-size:15px;font-weight:700;
    border-top:2px solid #C9A84C;border-left:4px solid #E8C97A;">
    <span>Estimated Total</span>
    <span style="color:#E8C97A;font-size:16px;">${d.totalAmount}</span>
  </div>
</div>
<div style="font-size:9.5px;color:#4A4A6A;font-style:italic;
  padding:6px 8px;border-left:3px solid #C9A84C;background:#F5F0E8;line-height:1.6;">
  Prices are best estimates of future market value, subject to change.<br/>
  Payments accepted: Check (payable to "The Caterer LLC") &nbsp;·&nbsp;
  Venmo (2% fee) &nbsp;·&nbsp; Credit/Debit (1.5%; MasterCard 3.5%)
</div>
</div>

<!-- ═══ TERMS & CONDITIONS ═══ -->
<div class="page-break">
  ${sectionBanner('Terms &amp; Conditions', `Contract ID: ${d.contractId.slice(0,8).toUpperCase()}`)}
  <div class="terms">
    <h4>Cancellation or Change of Date Policy</h4>
    <p>Over 12 months prior to the event — A $1,000 date freeze will be forfeited. We will attempt to reschedule your event (deposit is transferable; rebooking fee: $500).</p>
    <p>Within 6–12 months prior to the event — A maximum of 30% of the deposit minus the $1,000 date freeze will be refunded, depending on products purchased for the event.</p>
    <p>Within 6 months of the event — The deposit is forfeited; anything paid above the deposit will be refunded.</p>
    <p>Within 2 weeks — 100% of the contract total will be forfeited. Wedding cakes are subject to full 50% deposit loss after contract signing.</p>
    <h4>Guest Count Guarantee</h4>
    <p>Guarantee is 90% of the original contracted guest count. If you fall below 90%, the per-person rate is subject to change. Final guest count and any changes are due 3 weeks prior to the event date along with the remainder of the bill.</p>
    <h4>Rentals</h4>
    <p>All rental costs are subject to change by The Catering Company up to the final payment date to match market value.</p>
    <h4>Food Escalation</h4>
    <p>Food costs are subject to change in the event of escalation up to the final payment date to match market value.</p>
    <h4>Credit / Debit Fees</h4>
    <p>1.5% fee for all cards; MasterCard — 3.5%. Checks made out to "The Caterer LLC". Venmo — 2% fee will apply.</p>
    <h4>Additional Fees</h4>
    <p>For events where The Catering Company is not providing setup, onsite walk-throughs will have a $150 fee (plus possible fuel charges). Additional labor charges may apply over 6 hours of onsite service ($30/hr per server; $50/hr per supervisor or bartender). Setup and cleanup times do not count toward service hours (1.5 hrs setup, 1 hr cleanup).</p>
    <h4>Bartenders</h4>
    <p>This is a labor charge only. Ice, coolers, mixers, and drinks can be purchased separately. Liquor liability to be billed separately.</p>
    <h4>Last-Minute Changes</h4>
    <p>Any changes to the contract or labor due to weather, unforeseen services, etc., will be billed post-event and are due net 30.</p>
    <h4>Onsite Service</h4>
    <p>Includes chaffers, platters, service ware, equipment, and standard staffing. 9.4% tax and 20% service and gratuity charge apply to all events. 5% onsite service charge on full-service events.</p>
    <h4>Disposable Service</h4>
    <p>When disposable service is included, standard disposable plates, cutlery, and napkins are provided as specified in the event details above.</p>
    <p class="tfn">Taxes &amp; Fees: 9.4% Sales Tax &nbsp;·&nbsp; 6.5% Onsite Service Fee (full-service events)</p>
  </div>
</div>

<!-- ═══ SIGNATURES (dedicated last page) ═══ -->
<div class="page-break">
  ${sectionBanner('Signatures')}
  <div class="sig-intro">By signing below, both parties agree to the terms and conditions outlined in this contract.</div>
  <div class="sig-grid">
    <div class="sig-col">
      <span class="sig-label">Client Name (Print)</span>
      <div class="sig-name-line"></div>
      <div class="sig-inline">
        <div class="sp">
          <span class="sig-label">Client Signature</span>
          <div class="sig-line"></div>
        </div>
        <div class="sp date">
          <span class="sig-label">Date</span>
          <div class="sig-line"></div>
        </div>
      </div>
    </div>
    <div class="sig-col">
      <span class="sig-label">The Catering Company Representative</span>
      <div class="sig-name-line"></div>
      <div class="sig-inline">
        <div class="sp">
          <span class="sig-label">Authorized Signature</span>
          <div class="sig-line"></div>
        </div>
        <div class="sp date">
          <span class="sig-label">Date</span>
          <div class="sig-line"></div>
        </div>
      </div>
    </div>
  </div>
</div>

</body>
</html>`;
}

