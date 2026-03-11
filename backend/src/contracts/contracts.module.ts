import { Module } from '@nestjs/common';
import { BullModule } from '@nestjs/bullmq';
import { ContractsController } from './contracts.controller';
import { StaffContractsController } from './staff-contracts.controller';
import { ContractsService } from './contracts.service';
import { ContractPdfService } from './contract-pdf.service';
import { PrismaService } from '../prisma.service';
import { OpenSignModule } from '../opensign/opensign.module';
import { StaffGuard } from '../common/guards/staff.guard';

@Module({
  imports: [
    BullModule.registerQueue({
      name: 'pdf_generation',
    }),
    OpenSignModule,
  ],
  controllers: [ContractsController, StaffContractsController],
  providers: [ContractsService, ContractPdfService, PrismaService, StaffGuard],
  exports: [ContractsService],
})
export class ContractsModule {}
