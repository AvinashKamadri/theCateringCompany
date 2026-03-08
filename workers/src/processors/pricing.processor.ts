import { Job } from 'bullmq';
import { Decimal } from '@prisma/client/runtime/library';
import prisma from '../lib/prisma';
import { createJobLogger } from '../lib/logger';
import type { PricingJobData } from '../types/jobs';

const MARGIN_ALERT_THRESHOLD = parseFloat(process.env.MARGIN_ALERT_THRESHOLD || '15');

interface LineItem {
  description?: string;
  quantity?: number;
  unit_price?: number;
  amount?: number;
  cost?: number;
}

export async function processPricing(job: Job<PricingJobData>): Promise<void> {
  const { projectPricingId, changeOrderId, userId, projectId } = job.data;
  const log = createJobLogger('pricing', job.id!, userId, projectId);

  log.info({ projectPricingId, changeOrderId }, 'Processing pricing recalculation');

  const projectPricing = await prisma.project_pricing.findUnique({
    where: { id: projectPricingId },
  });

  if (!projectPricing) {
    log.warn({ projectPricingId }, 'Project pricing not found, skipping');
    return;
  }

  // Parse line_items from JSONB
  const lineItems = (projectPricing.line_items as LineItem[] | null) || [];

  log.info({ projectPricingId, lineItemCount: lineItems.length }, 'Recalculating totals from line items');

  // Calculate subtotal from line items
  let subtotal = 0;
  let totalCost = 0;

  for (const item of lineItems) {
    const itemAmount = item.amount ?? (item.quantity || 0) * (item.unit_price || 0);
    subtotal += itemAmount;
    totalCost += item.cost || 0;
  }

  // Retrieve existing adjustments or default to zero
  const tax = projectPricing.tax ? parseFloat(projectPricing.tax.toString()) : 0;
  const serviceCharge = projectPricing.service_charge ? parseFloat(projectPricing.service_charge.toString()) : 0;
  const adminFee = projectPricing.admin_fee ? parseFloat(projectPricing.admin_fee.toString()) : 0;
  const negotiatedAdjustment = projectPricing.negotiated_adjustment
    ? parseFloat(projectPricing.negotiated_adjustment.toString())
    : 0;

  const finalTotal = subtotal + tax + serviceCharge + adminFee + negotiatedAdjustment;

  log.info(
    { projectPricingId, subtotal, tax, serviceCharge, adminFee, negotiatedAdjustment, finalTotal },
    'Totals recalculated',
  );

  // Update project_pricing with new totals
  await prisma.project_pricing.update({
    where: { id: projectPricingId },
    data: {
      subtotal: new Decimal(subtotal.toFixed(2)),
      final_total: new Decimal(finalTotal.toFixed(2)),
    },
  });

  // Check if margin is below threshold
  if (subtotal > 0 && totalCost > 0) {
    const margin = ((subtotal - totalCost) / subtotal) * 100;

    log.info(
      { projectPricingId, margin: margin.toFixed(2), threshold: MARGIN_ALERT_THRESHOLD },
      'Checking margin against threshold',
    );

    if (margin < MARGIN_ALERT_THRESHOLD) {
      log.warn(
        { projectPricingId, margin: margin.toFixed(2), threshold: MARGIN_ALERT_THRESHOLD },
        'Margin below threshold, creating margin alert',
      );

      await prisma.margin_alerts.create({
        data: {
          project_id: projectPricing.project_id,
          threshold: new Decimal(MARGIN_ALERT_THRESHOLD.toFixed(2)),
          current_margin: new Decimal(margin.toFixed(2)),
          triggered_at: new Date(),
        },
      });

      log.info({ projectPricingId }, 'Margin alert created');
    }
  }

  log.info({ projectPricingId, finalTotal }, 'Pricing recalculation completed');
}
