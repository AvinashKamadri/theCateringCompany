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
        AND p.title NOT ILIKE 'Chat Project%'
      ORDER BY p.created_at DESC
      LIMIT 100
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
        coalesce(avg(guest_count) FILTER (WHERE guest_count IS NOT NULL), 0)  AS avg_guests,
        count(*) FILTER (WHERE created_via_ai_intake = true)::int             AS via_ai
      FROM projects
      WHERE deleted_at IS NULL
        AND title NOT ILIKE 'AI Catering Intake%'
        AND title NOT ILIKE 'Chat Project%'
    `;

    return {
      total: totals.total,
      by_status: {
        draft: totals.draft,
        active: totals.active,
        confirmed: totals.confirmed,
        completed: totals.completed,
        cancelled: totals.cancelled,
      },
      avg_guests: Math.round(Number(totals.avg_guests)),
      via_ai: totals.via_ai,
    };
  }
}
