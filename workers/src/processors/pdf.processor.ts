import { Job } from 'bullmq';
import prisma from '../lib/prisma';
import { createJobLogger } from '../lib/logger';
import type { PdfJobData } from '../types/jobs';

export async function processPdf(job: Job<PdfJobData>): Promise<void> {
  const { contractId, userId, projectId } = job.data;
  const log = createJobLogger('pdf', job.id!, userId, projectId);

  log.info({ contractId }, 'Processing PDF generation');

  const contract = await prisma.contracts.findUnique({
    where: { id: contractId },
  });

  if (!contract) {
    log.warn({ contractId }, 'Contract not found, skipping');
    return;
  }

  // Idempotency check - if pdf_path is already set, skip
  if (contract.pdf_path) {
    log.info({ contractId, pdfPath: contract.pdf_path }, 'PDF already generated, skipping');
    return;
  }

  log.info({ contractId }, 'Rendering HTML template from contract body');

  // Build HTML from contract body JSON
  const body = contract.body as Record<string, unknown>;
  const title = contract.title || 'Contract';
  const html = buildContractHtml(title, body);

  log.info({ contractId, htmlLength: html.length }, 'HTML template rendered');

  // TODO: Use puppeteer-core to generate PDF buffer
  // const browser = await puppeteer.launch({ ... });
  // const page = await browser.newPage();
  // await page.setContent(html);
  // const pdfBuffer = await page.pdf({ format: 'A4' });
  // await browser.close();

  // TODO: Upload to R2 storage
  // For now, mock the storage path
  const pdfPath = `contracts/${contractId}/contract.pdf`;

  log.info({ contractId, pdfPath }, 'PDF generated (mocked), updating contract record');

  // Update contract with the PDF path
  await prisma.contracts.update({
    where: { id: contractId },
    data: { pdf_path: pdfPath },
  });

  // Create events row for audit trail
  await prisma.events.create({
    data: {
      event_type: 'contract.pdf_generated',
      project_id: contract.project_id,
      actor_id: userId || null,
      payload: {
        contractId,
        pdfPath,
        versionNumber: contract.version_number,
      },
    },
  });

  log.info({ contractId, pdfPath }, 'PDF generation completed');
}

/**
 * Builds a basic HTML document from the contract body JSON.
 * In production this would use a proper templating engine.
 */
function buildContractHtml(title: string, body: Record<string, unknown>): string {
  const sections = Array.isArray(body.sections)
    ? (body.sections as Array<{ heading?: string; content?: string }>)
        .map(
          (s) => `
      <div class="section">
        ${s.heading ? `<h2>${escapeHtml(s.heading)}</h2>` : ''}
        ${s.content ? `<p>${escapeHtml(s.content)}</p>` : ''}
      </div>`,
        )
        .join('\n')
    : `<pre>${escapeHtml(JSON.stringify(body, null, 2))}</pre>`;

  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>${escapeHtml(title)}</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 40px; }
    h1 { color: #333; border-bottom: 2px solid #333; padding-bottom: 10px; }
    h2 { color: #555; margin-top: 24px; }
    .section { margin-bottom: 16px; }
    pre { white-space: pre-wrap; word-wrap: break-word; }
  </style>
</head>
<body>
  <h1>${escapeHtml(title)}</h1>
  ${sections}
</body>
</html>`;
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
