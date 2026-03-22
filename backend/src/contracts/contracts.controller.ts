import { Controller, Post, Get, Param, Body, UseGuards, NotFoundException, Res } from '@nestjs/common';
import { Response } from 'express';
import { ContractsService } from './contracts.service';
import { ContractPdfService } from './contract-pdf.service';
import { CurrentUser } from '../common/decorators/current-user.decorator';
import { Public } from '../common/decorators/public.decorator';
import { JwtAuthGuard } from '../common/guards/jwt-auth.guard';
import { PrismaService } from '../prisma.service';
import * as fs from 'fs';
import * as path from 'path';

@Controller()
@UseGuards(JwtAuthGuard)
export class ContractsController {
  constructor(
    private readonly contractsService: ContractsService,
    private readonly contractPdfService: ContractPdfService,
    private readonly prisma: PrismaService,
  ) {}

  private readonly STAFF_DOMAINS = ['@catering-company.com'];

  private isStaffEmail(email: string): boolean {
    return this.STAFF_DOMAINS.some((d) => email?.toLowerCase().endsWith(d));
  }

  /** GET /contracts — staff see all contracts; clients see only their own */
  @Get('contracts')
  async findAll(@CurrentUser() user: { userId: string; email: string }) {
    const include = {
      projects_contracts_project_idToprojects: {
        select: { id: true, title: true, event_date: true, guest_count: true, status: true },
      },
    };

    if (this.isStaffEmail(user.email)) {
      return this.prisma.contracts.findMany({
        where: {
          is_active: true,
          projects_contracts_project_idToprojects: { deleted_at: null },
        },
        include,
        orderBy: { created_at: 'desc' },
      });
    }

    return this.prisma.contracts.findMany({
      where: {
        is_active: true,
        projects_contracts_project_idToprojects: {
          deleted_at: null,
          OR: [
            { owner_user_id: user.userId },
            { project_collaborators: { some: { user_id: user.userId } } },
          ],
        },
      },
      include,
      orderBy: { created_at: 'desc' },
    });
  }

  /** GET /contracts/:id — single contract with its project */
  @Get('contracts/:id')
  async findOne(
    @Param('id') id: string,
    @CurrentUser() user: { userId: string },
  ) {
    const contract = await this.prisma.contracts.findFirst({
      where: { id },
      include: {
        projects_contracts_project_idToprojects: {
          select: {
            id: true,
            title: true,
            event_date: true,
            guest_count: true,
            status: true,
            ai_event_summary: true,
            venues: { select: { id: true, name: true, address: true } },
          },
        },
      },
    });

    if (!contract) throw new NotFoundException(`Contract ${id} not found`);
    return contract;
  }

  @Post('projects/:projectId/contracts')
  async createContract(
    @Param('projectId') projectId: string,
    @CurrentUser('userId') userId: string,
    @Body()
    body: {
      title?: string;
      body: any;
      status?: string;
      totalAmount?: number;
      contractGroupId?: string;
    },
  ) {
    return this.contractsService.createVersion(userId, projectId, body);
  }

  @Post('contracts/:id/generate-pdf')
  async generatePdf(
    @Param('id') id: string,
    @CurrentUser('userId') userId: string,
  ) {
    await this.contractsService.enqueuePdfGeneration(id, userId);
    return { message: 'PDF generation queued' };
  }

  /** GET /contracts/:id/pdf — serve the contract PDF file (public so browser can open in new tab) */
  @Public()
  @Get('contracts/:id/pdf')
  async servePdf(
    @Param('id') id: string,
    @Res() res: Response,
  ) {
    const contract = await this.prisma.contracts.findUnique({
      where: { id },
      select: { pdf_path: true },
    });

    if (!contract?.pdf_path) {
      throw new NotFoundException('PDF not yet generated for this contract');
    }

    const filePath = path.join(process.cwd(), contract.pdf_path);
    if (!fs.existsSync(filePath)) {
      throw new NotFoundException('PDF file not found on disk');
    }

    res.setHeader('Content-Type', 'application/pdf');
    res.setHeader('Content-Disposition', `inline; filename="contract-${id}.pdf"`);
    fs.createReadStream(filePath).pipe(res);
  }

  /** POST /contracts/:id/preview-pdf — generate PDF without approving (staff preview) */
  @Post('contracts/:id/preview-pdf')
  async previewPdf(
    @Param('id') id: string,
    @CurrentUser() user: { userId: string; email: string },
  ) {
    if (!this.isStaffEmail(user.email)) {
      throw new NotFoundException('Not found');
    }
    const pdfPath = await this.contractPdfService.generateSimpleContract(id);
    return { pdf_path: pdfPath };
  }
}
