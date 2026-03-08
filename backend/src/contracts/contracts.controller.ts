import { Controller, Post, Get, Param, Body, UseGuards } from '@nestjs/common';
import { ContractsService } from './contracts.service';
import { CurrentUser } from '../common/decorators/current-user.decorator';

@Controller()
@UseGuards()
export class ContractsController {
  constructor(private readonly contractsService: ContractsService) {}

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
}
