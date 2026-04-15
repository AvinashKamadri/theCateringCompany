import { Injectable, ForbiddenException } from '@nestjs/common';
import { PrismaService } from '../prisma.service';

const STAFF_DOMAIN = '@catering-company.com';

@Injectable()
export class CrmService {
  constructor(private readonly prisma: PrismaService) {}

  private assertStaff(email: string) {
    if (!email?.endsWith(STAFF_DOMAIN)) {
      throw new ForbiddenException('CRM access is restricted to staff accounts.');
    }
  }

  async getLeads(callerEmail: string) {
    this.assertStaff(callerEmail);

    const projects = await this.prisma.$queryRaw<any[]>`
      SELECT
        p.id,
        p.title,
        p.status,
        p.event_date,
        p.guest_count,
        p.created_at,
        p.created_via_ai_intake,
        u.email          AS client_email,
        (up.metadata->>'first_name') || ' ' || (up.metadata->>'last_name') AS client_name,
        (SELECT count(*)::int FROM contracts c WHERE c.project_id = p.id)                       AS contract_count,
        (SELECT count(*)::int FROM project_collaborators pc WHERE pc.project_id = p.id)         AS member_count,
        (SELECT coalesce(sum(amount), 0) FROM payments pay WHERE pay.project_id = p.id)::float  AS paid_amount
      FROM projects p
      JOIN users u ON u.id = p.owner_user_id
      LEFT JOIN user_profiles up ON up.user_id = u.id
      WHERE p.deleted_at IS NULL
        AND p.title NOT ILIKE 'AI Catering Intake%'
        AND p.title NOT ILIKE 'AI Intake%'
        AND p.title NOT ILIKE 'Chat Project%'
      ORDER BY p.created_at DESC
      LIMIT 500
    `;

    return projects.map((p) => ({
      id: p.id,
      title: p.title,
      status: p.status,
      event_date: p.event_date,
      guest_count: p.guest_count,
      created_at: p.created_at,
      created_via_ai_intake: p.created_via_ai_intake,
      client_name: p.client_name?.trim() || null,
      client_email: p.client_email,
      contract_count: Number(p.contract_count),
      member_count: Number(p.member_count),
      paid_amount: Number(p.paid_amount),
    }));
  }

  async getStats(callerEmail: string) {
    this.assertStaff(callerEmail);

    const [totals] = await this.prisma.$queryRaw<any[]>`
      SELECT
        count(*)::int                                                          AS total,
        count(*) FILTER (WHERE status = 'confirmed')::int                     AS confirmed,
        count(*) FILTER (WHERE status = 'completed')::int                     AS completed,
        count(*) FILTER (WHERE status = 'draft')::int                         AS draft,
        count(*) FILTER (WHERE status = 'active')::int                        AS active,
        count(*) FILTER (WHERE status = 'cancelled')::int                     AS cancelled,
        count(*) FILTER (WHERE status = 'rejected')::int                      AS rejected,
        coalesce(avg(guest_count) FILTER (WHERE guest_count IS NOT NULL), 0)  AS avg_guests,
        count(*) FILTER (WHERE created_via_ai_intake = true)::int             AS via_ai
      FROM projects
      WHERE deleted_at IS NULL
        AND title NOT ILIKE 'AI Catering Intake%'
        AND title NOT ILIKE 'AI Intake%'
        AND title NOT ILIKE 'Chat Project%'
    `;

    return {
      total: Number(totals.total),
      by_status: {
        draft:     Number(totals.draft),
        active:    Number(totals.active),
        confirmed: Number(totals.confirmed),
        completed: Number(totals.completed),
        cancelled: Number(totals.cancelled),
        rejected:  Number(totals.rejected),
      },
      avg_guests: Math.round(Number(totals.avg_guests)),
      via_ai: Number(totals.via_ai),
    };
  }

  async getAnalytics(callerEmail: string) {
    this.assertStaff(callerEmail);

    // Monthly bookings for last 12 months
    const monthly = await this.prisma.$queryRaw<any[]>`
      SELECT
        to_char(date_trunc('month', created_at), 'Mon YY') AS month,
        date_trunc('month', created_at)                    AS month_date,
        count(*)::int                                      AS bookings,
        coalesce(sum(guest_count), 0)::int                 AS total_guests
      FROM projects
      WHERE deleted_at IS NULL
        AND title NOT ILIKE 'AI Catering Intake%'
        AND title NOT ILIKE 'AI Intake%'
        AND title NOT ILIKE 'Chat Project%'
        AND created_at >= now() - interval '12 months'
      GROUP BY date_trunc('month', created_at)
      ORDER BY month_date ASC
    `;

    // Revenue from contracts (signed/completed)
    const revenueMonthly = await this.prisma.$queryRaw<any[]>`
      SELECT
        to_char(date_trunc('month', c.created_at), 'Mon YY') AS month,
        date_trunc('month', c.created_at)                    AS month_date,
        coalesce(sum(c.total_amount), 0)::float               AS revenue
      FROM contracts c
      WHERE c.status IN ('signed', 'approved', 'sent')
        AND c.total_amount IS NOT NULL
        AND c.created_at >= now() - interval '12 months'
      GROUP BY date_trunc('month', c.created_at)
      ORDER BY month_date ASC
    `;

    // Top event types by guest count (inferred from project titles)
    const guestBuckets = await this.prisma.$queryRaw<any[]>`
      SELECT
        CASE
          WHEN guest_count < 50  THEN 'Under 50'
          WHEN guest_count < 100 THEN '50–99'
          WHEN guest_count < 200 THEN '100–199'
          ELSE '200+'
        END AS bucket,
        count(*)::int AS count
      FROM projects
      WHERE deleted_at IS NULL
        AND guest_count IS NOT NULL
        AND title NOT ILIKE 'AI Catering Intake%'
        AND title NOT ILIKE 'AI Intake%'
      GROUP BY bucket
      ORDER BY min(guest_count) ASC
    `;

    return {
      monthly_bookings: monthly.map((r) => ({
        month: r.month,
        bookings: Number(r.bookings),
        total_guests: Number(r.total_guests),
      })),
      monthly_revenue: revenueMonthly.map((r) => ({
        month: r.month,
        revenue: Number(r.revenue),
      })),
      guest_buckets: guestBuckets.map((r) => ({
        bucket: r.bucket,
        count: Number(r.count),
      })),
    };
  }
}
