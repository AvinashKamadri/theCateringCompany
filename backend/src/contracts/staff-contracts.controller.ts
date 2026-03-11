import { Controller, Get, Post, Patch, Param, Body, UseGuards, Logger } from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { StaffGuard } from '../common/guards/staff.guard';
import { CurrentUser } from '../common/decorators/current-user.decorator';
import { ContractsService } from './contracts.service';
import { ContractPdfService } from './contract-pdf.service';
import { PrismaService } from '../prisma.service';

@UseGuards(AuthGuard('jwt'), StaffGuard)
@Controller('staff/contracts')
export class StaffContractsController {
  private readonly logger = new Logger(StaffContractsController.name);

  constructor(
    private readonly contractsService: ContractsService,
    private readonly contractPdfService: ContractPdfService,
    private readonly prisma: PrismaService,
  ) {}

  /**
   * GET /staff/contracts/pending
   * Get all contracts pending staff approval
   */
  @Get('pending')
  async getPendingContracts(@CurrentUser() user: { userId: string; email: string }) {
    this.logger.log(`📋 [Staff] ${user.email} fetching pending contracts`);

    const contracts = await this.prisma.contracts.findMany({
      where: {
        status: 'pending_staff_approval',
        deleted_at: null,
      },
      include: {
        projects_contracts_project_idToprojects: {
          select: {
            id: true,
            title: true,
            event_date: true,
            guest_count: true,
            ai_event_summary: true,
          },
        },
        users_contracts_created_byTousers: {
          select: {
            id: true,
            email: true,
          },
        },
      },
      orderBy: {
        created_at: 'desc',
      },
    });

    this.logger.log(`📊 [Staff] Found ${contracts.length} pending contracts`);

    return {
      contracts,
      count: contracts.length,
    };
  }

  /**
   * GET /staff/contracts/:id
   * Get contract details for review
   */
  @Get(':id')
  async getContractForReview(
    @Param('id') contractId: string,
    @CurrentUser() user: { userId: string; email: string },
  ) {
    this.logger.log(`📄 [Staff] ${user.email} reviewing contract ${contractId}`);

    const contract = await this.prisma.contracts.findUnique({
      where: { id: contractId },
      include: {
        projects_contracts_project_idToprojects: {
          select: {
            id: true,
            title: true,
            event_date: true,
            event_end_date: true,
            guest_count: true,
            ai_event_summary: true,
            venues: {
              select: {
                name: true,
                address: true,
              },
            },
          },
        },
        users_contracts_created_byTousers: {
          select: {
            id: true,
            email: true,
            primary_phone: true,
          },
        },
      },
    });

    if (!contract) {
      this.logger.warn(`⚠️ [Staff] Contract ${contractId} not found`);
      throw new Error('Contract not found');
    }

    return contract;
  }

  /**
   * POST /staff/contracts/:id/approve
   * Approve contract and send to SignWell
   */
  @Post(':id/approve')
  async approveContract(
    @Param('id') contractId: string,
    @CurrentUser() user: { userId: string; email: string },
    @Body() body: { message?: string; adjustments?: any },
  ) {
    try {
      this.logger.log(`✅ [Staff] ${user.email} approving contract ${contractId}`);
      console.log(`[DEBUG] Step 1: Starting approval for contract ${contractId}`);

    // Get contract with client info
    console.log('[DEBUG] Step 2: Fetching contract from database...');
    const contract = await this.prisma.contracts.findUnique({
      where: { id: contractId },
      include: {
        projects_contracts_project_idToprojects: {
          select: {
            ai_event_summary: true,
          },
        },
        users_contracts_created_byTousers: {
          select: {
            email: true,
          },
        },
      },
    });

    if (!contract) {
      console.log('[DEBUG] Step 3: ERROR - Contract not found!');
      throw new Error('Contract not found');
    }

    console.log('[DEBUG] Step 3: Contract found, extracting client info...');
    // Extract client info from contract body or ai_event_summary
    const contractBody = contract.body as any;
    console.log('[DEBUG] Step 4: Contract body:', JSON.stringify(contractBody, null, 2));

    const aiEventData = contract.projects_contracts_project_idToprojects?.ai_event_summary
      ? JSON.parse(contract.projects_contracts_project_idToprojects.ai_event_summary as string)
      : {};
    console.log('[DEBUG] Step 5: AI event data:', JSON.stringify(aiEventData, null, 2));

    const clientEmail =
      contractBody?.client_info?.email ||
      aiEventData.contact_email;

    const clientName =
      contractBody?.client_info?.name ||
      aiEventData.client_name ||
      contract.users_contracts_created_byTousers?.email.split('@')[0] || // Use email username as fallback
      'Client';

    console.log('[DEBUG] Step 6: Extracted - Email:', clientEmail, 'Name:', clientName);

    if (!clientEmail || !clientName) {
      console.log('[DEBUG] Step 7: ERROR - Missing client email or name!');
      throw new Error('Client email and name are required to send contract');
    }

    // Update contract status to sent (will be updated again after OpenSign call)
    const existingMetadata = contract.metadata as any || {};
    await this.prisma.contracts.update({
      where: { id: contractId },
      data: {
        status: 'sent',
        metadata: {
          ...existingMetadata,
          approved_by: user.email,
          approved_at: new Date().toISOString(),
          approval_message: body.message,
          adjustments: body.adjustments,
        },
      },
    });

    this.logger.log(`✅ [Staff] Contract ${contractId} approved by ${user.email}`);
    this.logger.log(`📧 [Staff] Preparing to send to OpenSign for client: ${clientName} (${clientEmail})`);

    console.log('[DEBUG] Step 8: Contract updated to approved status');

    // Check if PDF exists, if not, generate it now
    let pdfPath = contract.pdf_path;
    console.log('[DEBUG] Step 9: Checking PDF - current path:', pdfPath);
    if (!pdfPath) {
      this.logger.warn(`⚠️ [Staff] No PDF found for contract ${contractId}, generating now...`);
      console.log('[DEBUG] Step 10: Generating PDF...');
      pdfPath = await this.contractPdfService.generateSimpleContract(contractId);
      this.logger.log(`✅ [Staff] PDF generated at ${pdfPath}`);
      console.log('[DEBUG] Step 11: PDF generated successfully at:', pdfPath);
    }

    // Send to OpenSign for e-signature
    console.log('[DEBUG] Step 12: Sending to OpenSign...');
    try {
      const signWellDoc = await this.contractsService.sendToSignWell(
        contractId,
        [
          {
            email: clientEmail,
            name: clientName,
            role: 'signer',
          },
        ],
        pdfPath, // Pass the PDF path (generated or existing)
      );

      console.log('[DEBUG] Step 13: OpenSign response received:', signWellDoc);
      this.logger.log(`✅ [Staff] Contract ${contractId} sent to OpenSign successfully`);
      this.logger.log(`🔗 [Staff] OpenSign document ID: ${signWellDoc.id}`);
      this.logger.log(`📨 [Staff] Client will receive email at: ${clientEmail}`);

      return {
        success: true,
        message: 'Contract approved and sent to client for signature',
        opensign_document_id: signWellDoc.id,
        signing_url: signWellDoc.signing_url,
      };
    } catch (error: any) {
      console.log('[DEBUG] ERROR in OpenSign call:', error);
      this.logger.error(`❌ [Staff] Failed to send contract ${contractId} to OpenSign`, error.message);
      this.logger.error(`❌ [Staff] Error stack:`, error.stack);
      throw new Error(`Failed to send to OpenSign: ${error.message}`);
    }
    } catch (error: any) {
      console.log('[DEBUG] FATAL ERROR in approval:', error);
      this.logger.error(`❌ [Staff] Approval failed for contract ${contractId}`, error.message);
      this.logger.error(`❌ [Staff] Error details:`, error);
      throw error;
    }
  }

  /**
   * POST /staff/contracts/:id/reject
   * Reject contract
   */
  @Post(':id/reject')
  async rejectContract(
    @Param('id') contractId: string,
    @CurrentUser() user: { userId: string; email: string },
    @Body() body: { reason: string },
  ) {
    this.logger.log(`❌ [Staff] ${user.email} rejecting contract ${contractId}`);
    this.logger.log(`📝 [Staff] Reason: ${body.reason}`);

    const contract = await this.prisma.contracts.findUnique({
      where: { id: contractId },
      select: { metadata: true },
    });

    const existingMetadata = contract?.metadata as any || {};
    await this.prisma.contracts.update({
      where: { id: contractId },
      data: {
        status: 'rejected',
        metadata: {
          ...existingMetadata,
          rejected_by: user.email,
          rejected_at: new Date().toISOString(),
          rejection_reason: body.reason,
        },
      },
    });

    this.logger.log(`✅ [Staff] Contract ${contractId} rejected`);

    return {
      success: true,
      message: 'Contract rejected',
    };
  }

  /**
   * PATCH /staff/contracts/:id/pricing
   * Update contract pricing before approval
   */
  @Patch(':id/pricing')
  async updatePricing(
    @Param('id') contractId: string,
    @CurrentUser() user: { userId: string; email: string },
    @Body() body: { pricing: any },
  ) {
    this.logger.log(`💰 [Staff] ${user.email} updating pricing for contract ${contractId}`);

    const contract = await this.prisma.contracts.findUnique({
      where: { id: contractId },
    });

    if (!contract) {
      throw new Error('Contract not found');
    }

    // Update contract body with new pricing
    const existingBody = contract.body as any;
    const updatedBody = {
      ...existingBody,
      pricing: body.pricing,
    };

    const existingMetadata = contract.metadata as any || {};
    await this.prisma.contracts.update({
      where: { id: contractId },
      data: {
        body: updatedBody,
        total_amount: body.pricing.total || contract.total_amount,
        metadata: {
          ...existingMetadata,
          pricing_updated_by: user.email,
          pricing_updated_at: new Date().toISOString(),
        },
      },
    });

    this.logger.log(`✅ [Staff] Pricing updated for contract ${contractId}`);

    return {
      success: true,
      message: 'Pricing updated successfully',
    };
  }
}
