import { Module } from '@nestjs/common';
import { ContractsController } from './contracts.controller';
import { StaffContractsController } from './staff-contracts.controller';
import { ContractsService } from './contracts.service';
import { ContractPdfService } from './contract-pdf.service';
import { PrismaService } from '../prisma.service';
import { OpenSignModule } from '../opensign/opensign.module';
import { StaffGuard } from '../common/guards/staff.guard';
import { PricingService } from '../pricing/pricing.service';

@Module({
  imports: [OpenSignModule],
  controllers: [ContractsController, StaffContractsController],
  providers: [ContractsService, ContractPdfService, PrismaService, StaffGuard, PricingService],
  exports: [ContractsService],
})
export class ContractsModule {}
