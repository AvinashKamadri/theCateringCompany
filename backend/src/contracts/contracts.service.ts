import { Injectable } from '@nestjs/common';
import { InjectQueue } from '@nestjs/bullmq';
import { Queue } from 'bullmq';
import { randomUUID } from 'crypto';
import { PrismaService } from '../prisma.service';

@Injectable()
export class ContractsService {
  constructor(
    private readonly prisma: PrismaService,
    @InjectQueue('pdf_generation') private readonly pdfQueue: Queue,
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
}
