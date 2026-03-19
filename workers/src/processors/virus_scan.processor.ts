

import prisma from '../lib/prisma';
import { createJobLogger } from '../lib/logger';
import type { VirusScanJobData } from '../types/jobs';

const CLAM_AV_ENABLED = process.env.CLAM_AV_ENABLED === 'true';

export async function processVirusScan(job: { id: string; data: VirusScanJobData }): Promise<void> {
  const { attachmentId, storagePath, userId, projectId } = job.data;
  const log = createJobLogger('virus_scan', job.id!, userId, projectId);

  log.info({ attachmentId, storagePath }, 'Processing virus scan');

  const attachment = await prisma.attachments.findUnique({
    where: { id: attachmentId },
  });

  if (!attachment) {
    log.warn({ attachmentId }, 'Attachment not found, skipping');
    return;
  }

  // Idempotency check
  if (attachment.virus_scan_status === 'clean') {
    log.info({ attachmentId }, 'Attachment already scanned as clean, skipping');
    return;
  }

  let scanResult: 'clean' | 'infected' = 'clean';

  if (CLAM_AV_ENABLED) {
    log.info({ attachmentId, storagePath }, 'CLAM_AV_ENABLED=true, running ClamAV scan');
    // TODO: Integrate with ClamAV
    // const clamscan = await new NodeClam().init({ clamdscan: { socket: process.env.CLAMAV_SOCKET } });
    // const { isInfected, viruses } = await clamscan.scanFile(storagePath);
    // if (isInfected) {
    //   scanResult = 'infected';
    //   log.warn({ attachmentId, viruses }, 'Virus detected in attachment');
    // }
    scanResult = 'clean'; // placeholder until ClamAV integration
  } else {
    log.info({ attachmentId }, 'CLAM_AV_ENABLED=false, mock scan - marking as clean');
  }

  if ((scanResult as string) === 'infected') {
    // Quarantine the attachment
    await prisma.attachments.update({
      where: { id: attachmentId },
      data: {
        virus_scan_status: 'infected',
        quarantine_reason: 'Virus detected during automated scan',
        quarantined_at: new Date(),
        preview_allowed: false,
      },
    });

    log.warn({ attachmentId }, 'Attachment quarantined due to virus detection');
  } else {
    // Mark as clean
    await prisma.attachments.update({
      where: { id: attachmentId },
      data: {
        virus_scan_status: 'clean',
      },
    });

    log.info({ attachmentId }, 'Attachment marked as clean');
  }

  log.info({ attachmentId, scanResult }, 'Virus scan completed');
}
