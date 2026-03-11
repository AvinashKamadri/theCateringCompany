import { Injectable, Logger } from '@nestjs/common';
import { PrismaService } from '../prisma.service';
import * as fs from 'fs/promises';
import * as path from 'path';

@Injectable()
export class ContractPdfService {
  private readonly logger = new Logger(ContractPdfService.name);

  constructor(private readonly prisma: PrismaService) {}

  /**
   * Generate a simple text-based contract document
   * TODO: Replace with proper PDF generation using puppeteer or similar
   */
  async generateSimpleContract(contractId: string): Promise<string> {
    this.logger.log(`📄 Generating simple contract for ${contractId}`);

    const contract = await this.prisma.contracts.findUnique({
      where: { id: contractId },
      include: {
        projects_contracts_project_idToprojects: {
          select: {
            title: true,
            event_date: true,
            guest_count: true,
          },
        },
      },
    });

    if (!contract) {
      throw new Error('Contract not found');
    }

    const contractBody = contract.body as any;
    const project = contract.projects_contracts_project_idToprojects;

    // Generate simple text content
    const contractText = `
THE CATERING COMPANY
CATERING SERVICE AGREEMENT

Contract ID: ${contractId}
Date: ${new Date().toISOString().split('T')[0]}

-----------------------------------
EVENT DETAILS
-----------------------------------
Event: ${project?.title || 'Event'}
Date: ${project?.event_date ? new Date(project.event_date).toDateString() : 'TBD'}
Guest Count: ${project?.guest_count || 'TBD'}
Service Type: ${contractBody?.event_details?.service_type || 'Full Service'}

-----------------------------------
CLIENT INFORMATION
-----------------------------------
Name: ${contractBody?.client_info?.name || 'Client'}
Email: ${contractBody?.client_info?.email || 'N/A'}
Phone: ${contractBody?.client_info?.phone || 'N/A'}

-----------------------------------
MENU
-----------------------------------
${contractBody?.menu?.items?.join('\n') || 'Standard menu items'}

Dietary Restrictions: ${contractBody?.menu?.dietary_restrictions?.join(', ') || 'None'}

-----------------------------------
VENUE
-----------------------------------
${contractBody?.event_details?.venue?.name || 'TBD'}
${contractBody?.event_details?.venue?.address || ''}

-----------------------------------
TERMS & CONDITIONS
-----------------------------------
1. This is a binding agreement between The Catering Company and the Client
2. Payment terms and schedule to be determined
3. Cancellation policy applies as per company policy
4. All services subject to availability

-----------------------------------
SIGNATURES
-----------------------------------
By signing below, both parties agree to the terms outlined in this contract.

Client Signature: __________________ Date: __________

The Catering Company: __________________ Date: __________


This document serves as a legally binding contract.
`;

    // Create uploads directory if it doesn't exist
    const uploadsDir = path.join(process.cwd(), 'uploads', 'contracts');
    await fs.mkdir(uploadsDir, { recursive: true });

    // Save as text file (will be treated as PDF for SignWell)
    const filename = `contract-${contractId}-${Date.now()}.txt`;
    const filePath = path.join(uploadsDir, filename);
    await fs.writeFile(filePath, contractText, 'utf-8');

    this.logger.log(`✅ Contract document saved to ${filePath}`);

    // Update contract with file path
    const relativePath = `uploads/contracts/${filename}`;
    await this.prisma.contracts.update({
      where: { id: contractId },
      data: { pdf_path: relativePath },
    });

    return relativePath;
  }
}
