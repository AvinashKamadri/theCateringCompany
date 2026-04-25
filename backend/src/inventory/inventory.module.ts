import { Module } from '@nestjs/common';
import { InventoryController } from './inventory.controller';
import { InventoryService } from './inventory.service';
import { MenuAllergenDerivationService } from './menu-allergen-derivation.service';
import { PrismaService } from '../prisma.service';

@Module({
  controllers: [InventoryController],
  providers: [InventoryService, MenuAllergenDerivationService, PrismaService],
  exports: [MenuAllergenDerivationService],
})
export class InventoryModule {}
