/**
 * Idempotent backfill / drift-recovery for `menu_items.allergens`.
 *
 * Recomputes the cache for every menu_item from the ingredient graph.
 * Safe to run anytime — it only writes when the derived value differs
 * from what's already stored.
 *
 * Run with:
 *   npx ts-node backend/src/scripts/recompute-menu-allergens.ts
 *   npx ts-node backend/src/scripts/recompute-menu-allergens.ts --health
 */
import { Logger } from '@nestjs/common';
import { NestFactory } from '@nestjs/core';
import { Module } from '@nestjs/common';
import { PrismaService } from '../prisma.service';
import { MenuAllergenDerivationService } from '../inventory/menu-allergen-derivation.service';

@Module({ providers: [PrismaService, MenuAllergenDerivationService] })
class RecomputeModule {}

async function main() {
  const log = new Logger('recompute-menu-allergens');
  const app = await NestFactory.createApplicationContext(RecomputeModule, { logger: ['log', 'warn', 'error'] });
  const svc = app.get(MenuAllergenDerivationService);

  const wantHealth = process.argv.includes('--health');

  if (wantHealth) {
    const health = await svc.healthCheck();
    log.log('--- DATA HEALTH ---');
    log.log(JSON.stringify(health, null, 2));
  }

  log.log('Recomputing allergen cache for all menu_items...');
  const result = await svc.recomputeAll();
  log.log(`scanned=${result.scanned} changed=${result.changed} failed=${result.failed}`);

  await app.close();
  process.exit(result.failed > 0 ? 1 : 0);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
