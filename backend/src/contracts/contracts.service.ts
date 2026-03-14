import { Injectable } from '@nestjs/common';
import { InjectQueue } from '@nestjs/bullmq';
import { Queue } from 'bullmq';
import { randomUUID } from 'crypto';
import { PrismaService } from '../prisma.service';
import { OpenSignService } from '../opensign/opensign.service';

@Injectable()
export class ContractsService {
  constructor(
    private readonly prisma: PrismaService,
    @InjectQueue('pdf_generation') private readonly pdfQueue: Queue,
    private readonly openSignService: OpenSignService,
  ) {}

  /**
   * Create a new contract version for a project.
   *
   * Versioning logic:
   * - If contractGroupId is not provided, generate one with randomUUID().
   * - Query existing contracts with the same contract_group_id, get max version_number.
   * - Insert with version_number = max + 1 (or 1 if first version).
   * - Set previous_version_id to the ID of the previous latest version.
   * - Set created_by to the current user.
   * - Default status is 'draft'.
   */
  async createVersion(
    userId: string,
    projectId: string,
    dto: {
      title?: string;
      body: any;
      status?: string;
      totalAmount?: number;
      contractGroupId?: string;
    },
  ) {
    const contractGroupId = dto.contractGroupId ?? randomUUID();

    return this.prisma.$transaction(async (tx) => {
      // Find the latest existing contract in this group
      const previousVersion = await tx.contracts.findFirst({
        where: { contract_group_id: contractGroupId },
        orderBy: { version_number: 'desc' },
        select: { id: true, version_number: true },
      });

      const nextVersionNumber = previousVersion
        ? previousVersion.version_number + 1
        : 1;

      const previousVersionId = previousVersion ? previousVersion.id : null;

      const contract = await tx.contracts.create({
        data: {
          contract_group_id: contractGroupId,
          version_number: nextVersionNumber,
          previous_version_id: previousVersionId,
          project_id: projectId,
          status: (dto.status as any) ?? 'draft',
          title: dto.title ?? null,
          body: dto.body,
          total_amount: dto.totalAmount ?? null,
          is_active: true,
          created_by: userId,
        },
      });

      return contract;
    });
  }

  /**
   * Enqueue a PDF generation job for a contract.
   */
  async enqueuePdfGeneration(contractId: string, userId: string) {
    await this.pdfQueue.add('pdf_generation', {
      contractId,
      userId,
    });
  }

  /**
   * Send contract to SignWell for e-signature
   */
  // Renamed from sendToSignWell - now uses OpenSign
  async sendToSignWell(
    contractId: string,
    recipients: Array<{ email: string; name: string; role?: 'signer' | 'cc' }>,
    pdfUrl?: string,
  ) {
    // Get contract details
    const contract = await this.prisma.contracts.findUnique({
      where: { id: contractId },
      include: {
        projects_contracts_project_idToprojects: {
          select: {
            title: true,
            ai_event_summary: true,
          },
        },
      },
    });

    if (!contract) {
      throw new Error(`Contract ${contractId} not found`);
    }

    // If pdfUrl is a local file path, convert to base64
    let fileBase64: string | undefined;
    if (pdfUrl && !pdfUrl.startsWith('http')) {
      const fs = await import('fs/promises');
      const path = await import('path');
      const filePath = path.join(process.cwd(), pdfUrl);
      console.log(`[DocuSeal] Reading PDF from: ${filePath}`);
      const fileBuffer = await fs.readFile(filePath);
      fileBase64 = fileBuffer.toString('base64');
      console.log(`[DocuSeal] PDF loaded: ${Math.round(fileBuffer.length / 1024)}KB → base64 ${Math.round(fileBase64.length / 1024)}KB`);
      pdfUrl = undefined; // Clear pdfUrl since we're using base64
    }

    if (!fileBase64 && !pdfUrl) {
      throw new Error('Cannot send contract to DocuSeal: no PDF available. Generate the PDF first.');
    }

    // Send to OpenSign
    const openSignDoc = await this.openSignService.sendDocumentForSignature({
      name: contract.title || `Contract ${contractId}`,
      recipients,
      file_url: pdfUrl,
      file_base64: fileBase64,
      message: `Hi {{submitter.name}},\n\nThank you for choosing The Catering Company! Your catering contract for ${contract.projects_contracts_project_idToprojects?.title || 'your event'} is ready for your review and signature.\n\nClick the link below to review and sign your contract:\n{{submitter.link}}\n\nIf you have any questions or would like to make changes before signing, reply to this email or call us at 540-868-8410.\n\nWe look forward to making your event a success!\n\n— The Catering Company Team`,
      redirect_url: `${process.env.CORS_ORIGIN}/contracts/${contractId}/signed`,
    });

    // Update contract with OpenSign document ID — preserve existing metadata
    const existing = await this.prisma.contracts.findUnique({
      where: { id: contractId },
      select: { metadata: true },
    });
    const existingMeta = (existing?.metadata as any) || {};
    await this.prisma.contracts.update({
      where: { id: contractId },
      data: {
        status: 'sent',
        metadata: {
          ...existingMeta,
          opensign_document_id: openSignDoc.id,
          opensign_status: openSignDoc.status,
          opensign_signing_url: openSignDoc.signing_url,
          sent_for_signature_at: new Date().toISOString(),
        },
      },
    });

    return openSignDoc;
  }

  /**
   * Handle SignWell webhook events
   */
  async handleSignWellWebhook(event: any) {
    const { document_id, event_type, document } = event;

    // Find contract by OpenSign document ID
    const contract = await this.prisma.contracts.findFirst({
      where: {
        metadata: {
          path: ['opensign_document_id'],
          equals: document_id,
        },
      },
    });

    if (!contract) {
      console.warn(`Contract not found for SignWell document ${document_id}`);
      return;
    }

    // Update contract based on event type
    switch (event_type) {
      case 'document.completed':
        const completedMetadata = contract.metadata as any || {};
        await this.prisma.contracts.update({
          where: { id: contract.id },
          data: {
            status: 'signed',
            metadata: {
              ...completedMetadata,
              signwell_status: 'completed',
              signed_at: document.completed_at,
            },
          },
        });
        break;

      case 'document.declined':
        const declinedMetadata = contract.metadata as any || {};
        await this.prisma.contracts.update({
          where: { id: contract.id },
          data: {
            status: 'rejected',
            metadata: {
              ...declinedMetadata,
              signwell_status: 'declined',
            },
          },
        });
        break;

      case 'recipient.signed':
        // Update metadata with recipient signature info
        const existingMetadata = contract.metadata as any || {};
        const updatedMetadata = {
          ...existingMetadata,
          recipient_signatures: [
            ...(existingMetadata.recipient_signatures || []),
            {
              email: event.recipient.email,
              signed_at: event.signed_at,
            },
          ],
        };
        await this.prisma.contracts.update({
          where: { id: contract.id },
          data: { metadata: updatedMetadata },
        });
        break;
    }
  }
}
