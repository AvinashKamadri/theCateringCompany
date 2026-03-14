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
var ContractPdfService_1;
Object.defineProperty(exports, "__esModule", { value: true });
exports.ContractPdfService = void 0;
const common_1 = require("@nestjs/common");
const prisma_service_1 = require("../prisma.service");
const fs = require("fs/promises");
const path = require("path");
let ContractPdfService = ContractPdfService_1 = class ContractPdfService {
    constructor(prisma) {
        this.prisma = prisma;
        this.logger = new common_1.Logger(ContractPdfService_1.name);
    }
    async generateSimpleContract(contractId) {
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
        if (!contract)
            throw new Error('Contract not found');
        const body = contract.body || {};
        const project = contract.projects_contracts_project_idToprojects;
        const creatorEmail = contract.users_contracts_created_byTousers?.email || '';
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
        const parseCommaSep = (v) => {
            if (!v || v === 'none' || v === 'no')
                return [];
            if (Array.isArray(v))
                return v.filter(Boolean);
            return String(v).split(',').map((s) => s.trim()).filter(Boolean);
        };
        const menuItems = menuData.items?.length
            ? menuData.items.map((i) => (typeof i === 'string' ? i : i.name || i)).filter(Boolean)
            : [...parseCommaSep(slots.selected_dishes), ...parseCommaSep(slots.appetizers)];
        const dietaryRestrictions = menuData.dietary_restrictions || (slots.dietary_concerns ? [slots.dietary_concerns] : []);
        const addons = additional.addons || [];
        const modifications = additional.modifications || [];
        const pricing = body.pricing || {};
        const lineItems = Array.isArray(pricing.lineItems) ? pricing.lineItems : [];
        const lineSubtotal = lineItems.reduce((s, i) => s + i.quantity * i.unitPrice, 0);
        const subtotal = pricing.subtotal > 0 ? pricing.subtotal : (lineItems.length > 0 ? lineSubtotal : 0);
        const tax = subtotal > 0 ? subtotal * 0.094 : 0;
        const gratuity = subtotal > 0 ? subtotal * 0.20 : 0;
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
            menuItems,
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
        const uploadsDir = path.join(process.cwd(), 'uploads', 'contracts');
        await fs.mkdir(uploadsDir, { recursive: true });
        const filename = `contract-${contractId}-${Date.now()}.pdf`;
        const filePath = path.join(uploadsDir, filename);
        let pdfBuffer;
        try {
            const puppeteer = await Promise.resolve().then(() => require('puppeteer'));
            const browser = await puppeteer.default.launch({
                headless: true,
                args: ['--no-sandbox', '--disable-setuid-sandbox'],
            });
            const page = await browser.newPage();
            await page.setContent(html, { waitUntil: 'networkidle0' });
            pdfBuffer = Buffer.from(await page.pdf({
                format: 'Letter',
                printBackground: true,
                margin: { top: '0.75in', bottom: '0.75in', left: '0.75in', right: '0.75in' },
            }));
            await browser.close();
        }
        catch (err) {
            this.logger.error('Puppeteer PDF generation failed, falling back to text', err.message);
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
};
exports.ContractPdfService = ContractPdfService;
exports.ContractPdfService = ContractPdfService = ContractPdfService_1 = __decorate([
    (0, common_1.Injectable)(),
    __metadata("design:paramtypes", [prisma_service_1.PrismaService])
], ContractPdfService);
function row(label, value) {
    if (!value)
        return '';
    return `<tr><td class="lbl">${label}</td><td class="val">${value}</td></tr>`;
}
function bulletList(items) {
    if (!items.length)
        return '<p style="color:#888;font-size:12px">None specified</p>';
    return `<ul>${items.map(i => `<li>${i}</li>`).join('')}</ul>`;
}
function buildContractHtml(d) {
    return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: Arial, Helvetica, sans-serif; font-size: 13px; color: #1a1a1a; line-height: 1.5; }

  /* ── Header ── */
  .header { display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 3px solid #1a1a1a; padding-bottom: 12px; margin-bottom: 18px; }
  .company-name { font-size: 22px; font-weight: 700; letter-spacing: 0.5px; }
  .company-sub { font-size: 11px; color: #555; margin-top: 2px; }
  .header-right { text-align: right; font-size: 11px; color: #555; }
  .header-right strong { font-size: 13px; color: #1a1a1a; }

  /* ── Section header ── */
  .section { margin-bottom: 18px; }
  .section-title { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #fff; background: #1a1a1a; padding: 4px 8px; margin-bottom: 8px; }
  .section-title.light { background: #555; }

  /* ── Info table ── */
  table.info { width: 100%; border-collapse: collapse; margin-bottom: 4px; }
  table.info td { padding: 3px 6px; vertical-align: top; }
  table.info td.lbl { width: 38%; font-weight: 700; color: #444; font-size: 11px; text-transform: uppercase; letter-spacing: 0.3px; }
  table.info td.val { color: #1a1a1a; }

  /* ── Two-column event grid ── */
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 0 24px; }

  /* ── Menu lists ── */
  ul { padding-left: 18px; margin: 4px 0; }
  li { margin-bottom: 3px; }

  /* ── Billing box ── */
  .billing-box { border: 2px solid #1a1a1a; border-radius: 4px; padding: 10px 14px; margin-bottom: 18px; }
  .billing-row { display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid #eee; }
  .billing-row:last-child { border-bottom: none; font-weight: 700; font-size: 14px; }

  /* ── Signature block ── */
  .sig-block { margin-top: 24px; }
  .sig-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 18px; }
  .sig-line { margin-top: 32px; border-top: 1px solid #1a1a1a; padding-top: 4px; font-size: 11px; color: #555; }
  .sig-label { font-size: 11px; color: #555; margin-bottom: 2px; }

  /* ── Terms ── */
  .terms { font-size: 10.5px; color: #333; line-height: 1.6; }
  .terms h4 { font-size: 10.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; margin: 10px 0 2px; }
  .terms p { margin-bottom: 6px; }

  /* ── Page break ── */
  .page-break { page-break-before: always; margin-top: 0; }

  /* ── Footer ── */
  .footer { margin-top: 24px; border-top: 1px solid #ccc; padding-top: 8px; font-size: 10px; color: #777; text-align: center; }
</style>
</head>
<body>

<!-- ═══════════════ HEADER ═══════════════ -->
<div class="header">
  <div>
    <div class="company-name">The Catering Company</div>
    <div class="company-sub">Catering Service Agreement</div>
  </div>
  <div class="header-right">
    <div><strong>Contract Date:</strong> ${d.createdAt}</div>
    <div>info@thecatering-company.com</div>
    <div>540-868-8410</div>
    <div>1930 Front Royal Pike, Winchester VA 22602</div>
  </div>
</div>

<!-- ═══════════════ CLIENT & EVENT ═══════════════ -->
<div class="section">
  <div class="section-title">Event &amp; Client Information</div>
  <div class="grid2">
    <table class="info">
      ${row('Client Name', d.clientName)}
      ${row('Email', d.clientEmail)}
      ${row('Phone', d.clientPhone)}
    </table>
    <table class="info">
      ${row('Event Date', d.eventDate)}
      ${row('Event Type', d.eventType)}
      ${row('Guest Count', d.guestCount ? `${d.guestCount} guests (Guarantee: ${Math.ceil(Number(d.guestCount) * 0.9)} at 90%)` : '')}
      ${row('Service Style', d.serviceType)}
    </table>
  </div>
  ${d.venueName ? `
  <table class="info" style="margin-top:6px">
    ${row('Venue', d.venueName + (d.venueAddress ? ', ' + d.venueAddress : ''))}
  </table>` : ''}
</div>

<!-- ═══════════════ MENU ═══════════════ -->
${d.menuItems.length > 0 ? `
<div class="section">
  <div class="section-title">Menu</div>
  ${bulletList(d.menuItems)}
  ${d.dietaryRestrictions.length > 0 ? `
  <div style="margin-top:8px">
    <strong style="font-size:11px;text-transform:uppercase;color:#555">Dietary Restrictions / Allergies:</strong>
    <span> ${d.dietaryRestrictions.join(', ')}</span>
  </div>` : ''}
</div>` : ''}

<!-- ═══════════════ ADD-ONS & REQUESTS ═══════════════ -->
${(d.addons.length > 0 || d.modifications.length > 0) ? `
<div class="section">
  <div class="section-title light">Add-ons &amp; Special Requests</div>
  ${d.addons.length > 0 ? `<div><strong>Add-ons:</strong></div>${bulletList(d.addons)}` : ''}
  ${d.modifications.length > 0 ? `<div style="margin-top:6px"><strong>Special Requests / Modifications:</strong></div>${bulletList(d.modifications)}` : ''}
</div>` : ''}

<!-- ═══════════════ CONTRACT SUMMARY ═══════════════ -->
${d.contractSummary ? `
<div class="section">
  <div class="section-title light">Service Notes</div>
  <div style="font-size:12px;white-space:pre-wrap;line-height:1.6">${d.contractSummary}</div>
</div>` : ''}

<!-- ═══════════════ BILLING ═══════════════ -->
<div class="section">
  <div class="section-title">Billing Summary</div>
  <div class="billing-box">
    ${d.lineItems.length > 0 ? d.lineItems.map(item => `
    <div class="billing-row">
      <span>${item.description}${item.quantity > 1 ? ` &times; ${item.quantity}` : ''}</span>
      <span>$${(item.quantity * item.unitPrice).toLocaleString()}</span>
    </div>`).join('') : ''}
    ${d.tax > 0 ? `
    <div class="billing-row" style="color:#555">
      <span>Tax (9.4%)</span>
      <span>$${d.tax.toLocaleString()}</span>
    </div>` : ''}
    ${d.gratuity > 0 ? `
    <div class="billing-row" style="color:#555">
      <span>Service &amp; Gratuity (20%)</span>
      <span>$${d.gratuity.toLocaleString()}</span>
    </div>` : ''}
    <div class="billing-row">
      <span>Deposit Due at Time of Signing (50%)</span>
      <span>${d.deposit !== 'TBD' ? d.deposit : 'TBD'}</span>
    </div>
    <div class="billing-row">
      <span>Final Guest Count &amp; Remainder Due</span>
      <span>3 weeks prior to event</span>
    </div>
    <div class="billing-row">
      <span><strong>Estimated Total</strong></span>
      <span><strong>${d.totalAmount}</strong></span>
    </div>
  </div>
  <p style="font-size:11px;color:#555">Prices are best estimates of future market value, subject to change.<br/>
  Payments accepted: Check (payable to "The Caterer LLC"), Venmo (2% fee), Credit/Debit (1.5%; MasterCard 3.5%).</p>
</div>

<!-- ═══════════════ SIGNATURES ═══════════════ -->
<div class="sig-block">
  <div class="section-title">Signatures</div>
  <p style="font-size:12px;margin-bottom:16px">By signing below, both parties agree to the terms and conditions outlined in this contract.</p>
  <div class="sig-grid">
    <div>
      <div class="sig-label">Client Name (Print)</div>
      <div class="sig-line">&nbsp;</div>
      <div class="sig-label" style="margin-top:20px">Client Signature</div>
      <div class="sig-line">&nbsp;</div>
      <div class="sig-label" style="margin-top:20px">Date</div>
      <div class="sig-line">&nbsp;</div>
    </div>
    <div>
      <div class="sig-label">The Catering Company Representative</div>
      <div class="sig-line">&nbsp;</div>
      <div class="sig-label" style="margin-top:20px">Authorized Signature</div>
      <div class="sig-line">&nbsp;</div>
      <div class="sig-label" style="margin-top:20px">Date</div>
      <div class="sig-line">&nbsp;</div>
    </div>
  </div>
</div>

<!-- ═══════════════ TERMS (page 2) ═══════════════ -->
<div class="page-break">
  <div class="header" style="margin-bottom:14px">
    <div class="company-name" style="font-size:16px">Terms &amp; Conditions</div>
    <div class="header-right">Contract ID: <strong>${d.contractId.slice(0, 8).toUpperCase()}</strong></div>
  </div>

  <div class="terms">
    <h4>Cancellation or Change of Date Policy</h4>
    <p>Over 12 months prior to the event — A $1,000 date freeze will be forfeited. We will attempt to reschedule your event (deposit is transferable; rebooking fee: $500).</p>
    <p>Within 6–12 months prior to the event — A maximum of 30% of the deposit minus the $1,000 date freeze will be refunded, depending on products purchased for the event.</p>
    <p>Within 6 months of the event — The deposit is forfeited; anything paid above the deposit will be refunded.</p>
    <p>Within 2 weeks — 100% of the contract total will be forfeited.</p>
    <p>Wedding cakes are subject to full 50% deposit loss after contract signing.</p>

    <h4>Guest Count Guarantee</h4>
    <p>Guarantee is 90% of the original contracted guest count. If you fall below 90% of the guest count, the per-person rate is subject to change. Final guest count and any changes are due 3 weeks prior to the event date along with the remainder of the bill.</p>

    <h4>Rentals</h4>
    <p>All rental costs are subject to change by The Catering Company up to the final payment date to match market value.</p>

    <h4>Food Escalation</h4>
    <p>Food costs are subject to change in the event of escalation up to the final payment date to match market value.</p>

    <h4>Credit / Debit Fees</h4>
    <p>1.5% fee for all cards; MasterCard — 3.5%. Checks made out to "The Caterer LLC". Venmo — 2% fee will apply.</p>

    <h4>Additional Fees</h4>
    <p>For events where The Catering Company is not providing setup, onsite walk-throughs will have a $150 fee (plus possible fuel charges).</p>
    <p>Additional labor charges may apply over 6 hours of onsite service ($30/hr per server; $50/hr per supervisor or bartender). Setup and cleanup times do not count toward service hours (1.5 hrs setup, 1 hr cleanup).</p>

    <h4>Bartenders</h4>
    <p>This is a labor charge only. Ice, coolers, mixers, and drinks can be purchased separately. Liquor liability to be billed separately.</p>

    <h4>Last-Minute Changes</h4>
    <p>Any changes to the contract or labor due to weather, unforeseen services, etc., will be billed post-event and are due net 30.</p>

    <h4>Onsite Service</h4>
    <p>Includes chaffers, platters, service ware, equipment, and standard staffing. 9.4% tax and 20% service and gratuity charge apply to all events. 5% onsite service charge on full-service events.</p>

    <h4>Disposable Service</h4>
    <p>When disposable service is included, standard disposable plates, cutlery, and napkins are provided as specified in the event details above.</p>
  </div>
</div>

<div class="footer">
  The Catering Company &nbsp;|&nbsp; info@thecatering-company.com &nbsp;|&nbsp; 540-868-8410 &nbsp;|&nbsp; 1930 Front Royal Pike, Winchester VA 22602
</div>

</body>
</html>`;
}
//# sourceMappingURL=contract-pdf.service.js.map