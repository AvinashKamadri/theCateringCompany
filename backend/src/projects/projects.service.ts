import {
  Injectable,
  NotFoundException,
  ForbiddenException,
  ConflictException,
  Inject,
  forwardRef,
} from '@nestjs/common';
import { PrismaService } from '../prisma.service';
import { ContractsService } from '../contracts/contracts.service';

export const COLLABORATOR_ROLES = ['owner', 'manager', 'collaborator', 'viewer'] as const;
export type CollaboratorRole = typeof COLLABORATOR_ROLES[number];

// Roles that can manage (add/remove/update) other collaborators
const MANAGE_ROLES: CollaboratorRole[] = ['owner', 'manager'];
// Role hierarchy for permission checks (higher index = higher level)
const ROLE_RANK: Record<CollaboratorRole, number> = { owner: 4, manager: 3, collaborator: 2, viewer: 1 };

@Injectable()
export class ProjectsService {
  constructor(
    private readonly prisma: PrismaService,
    @Inject(forwardRef(() => ContractsService))
    private readonly contractsService: ContractsService,
  ) {}

  /**
   * Find all projects accessible by a user.
   * A project is accessible if the user is the owner (owner_user_id)
   * OR if the user exists in project_collaborators for that project.
   */
  async findAllForUser(userId: string, q?: string, status?: string, role?: string) {
    const isStaff = role === 'staff';
    const projects = await this.prisma.projects.findMany({
      where: {
        deleted_at: null,
        NOT: [
          { title: { startsWith: 'AI Catering Intake', mode: 'insensitive' } },
          { title: { startsWith: 'AI Intake', mode: 'insensitive' } },
          { title: { startsWith: 'Chat Project', mode: 'insensitive' } },
          { title: { contains: 'intake', mode: 'insensitive' } },
        ],
        // Staff sees all projects; hosts see only their own
        ...(isStaff ? {} : {
          OR: [
            { owner_user_id: userId },
            {
              project_collaborators: {
                some: { user_id: userId },
              },
            },
          ],
        }),
        ...(status && status !== 'all' ? { status: status as any } : {}),
        ...(q && q.trim().length >= 1 ? {
          AND: [{
            OR: [
              { title: { contains: q.trim(), mode: 'insensitive' } },
              { venues: { name: { contains: q.trim(), mode: 'insensitive' } } },
              { events: { some: { event_type: { contains: q.trim(), mode: 'insensitive' } } } },
              ...(isNaN(Number(q.trim())) ? [] : [{ guest_count: Number(q.trim()) }]),
            ],
          }],
        } : {}),
      },
      include: {
        venues: {
          select: {
            id: true,
            name: true,
          },
        },
        project_pricing: {
          select: {
            id: true,
            project_id: true,
          },
          take: 1,
        },
        events: {
          select: {
            id: true,
            event_type: true,
          },
          take: 1,
        },
      },
      orderBy: { created_at: 'desc' },
    });

    // Transform the response to flatten the structure
    return projects.map((project: any) => ({
      id: project.id,
      name: project.title,
      event_type: project.events?.[0]?.event_type || 'general',
      event_date: project.event_date,
      event_end_date: project.event_end_date,
      guest_count: project.guest_count,
      status: project.status,
      total_price: null, // Will be populated when pricing is available
      venue_name: project.venues?.name,
      venue_id: project.venue_id,
      created_at: project.created_at,
      updated_at: project.updated_at,
    }));
  }

  /**
   * Full-text search across a user's projects.
   * Matches against title, venue name, and event type using ILIKE.
   */
  async search(userId: string, query: string) {
    const q = `%${query.trim()}%`;
    const projects = await this.prisma.projects.findMany({
      where: {
        deleted_at: null,
        OR: [
          { owner_user_id: userId },
          { project_collaborators: { some: { user_id: userId } } },
        ],
        AND: [
          {
            OR: [
              { title: { contains: query.trim(), mode: 'insensitive' } },
              { venues: { name: { contains: query.trim(), mode: 'insensitive' } } },
              { events: { some: { event_type: { contains: query.trim(), mode: 'insensitive' } } } },
            ],
          },
        ],
      },
      include: {
        venues: { select: { id: true, name: true } },
        events: { select: { id: true, event_type: true }, take: 1 },
      },
      orderBy: { created_at: 'desc' },
      take: 20,
    });

    return projects.map((project: any) => ({
      id: project.id,
      name: project.title,
      event_type: project.events?.[0]?.event_type || 'general',
      event_date: project.event_date,
      guest_count: project.guest_count,
      status: project.status,
      venue_name: project.venues?.name,
      created_at: project.created_at,
    }));
  }

  /**
   * Find a project by ID, including the latest active contract metadata.
   * The latest active contract is determined by:
   *   - project_id matches
   *   - is_active = true
   *   - ordered by version_number DESC
   *   - take 1
   */
  async findById(id: string) {
    const project = await this.prisma.projects.findFirst({
      where: { id, deleted_at: null },
      include: {
        contracts_contracts_project_idToprojects: {
          where: { is_active: true },
          orderBy: { version_number: 'desc' },
          take: 1,
        },
      },
    });

    if (!project) {
      throw new NotFoundException(`Project with id ${id} not found`);
    }

    const latestActiveContract =
      project.contracts_contracts_project_idToprojects.length > 0
        ? project.contracts_contracts_project_idToprojects[0]
        : null;

    const { contracts_contracts_project_idToprojects, ...projectData } = project;

    return {
      ...projectData,
      latestActiveContract,
    };
  }

  /**
   * Create a new project and add the owner as a collaborator.
   * Uses a transaction to ensure both operations succeed or fail together.
   */
  async create(
    userId: string,
    dto: {
      title: string;
      eventDate?: string;
      eventEndDate?: string;
      guestCount?: number;
    },
  ) {
    return this.prisma.$transaction(async (tx) => {
      const project = await tx.projects.create({
        data: {
          owner_user_id: userId,
          title: dto.title,
          event_date: dto.eventDate ? new Date(dto.eventDate) : null,
          event_end_date: dto.eventEndDate ? new Date(dto.eventEndDate) : null,
          guest_count: dto.guestCount ?? null,
        },
      });

      await tx.project_collaborators.create({
        data: {
          project_id: project.id,
          user_id: userId,
          role: 'owner',
          added_by: userId,
        },
      });

      return project;
    });
  }

  // ─── Join Code Helpers ─────────────────────────────────────────────────────

  /** Derives a human-readable join code from project title + first 8 hex chars of the UUID. */
  generateJoinCode(project: { title: string; id: string }): string {
    const slug = project.title
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 30);
    const hexId = project.id.replace(/-/g, '').slice(0, 8);
    return slug ? `${slug}-${hexId}` : hexId;
  }

  /** Look up a project by its join code. The last 8 chars of the code are the hex prefix. */
  async findByJoinCode(code: string): Promise<{ id: string; title: string; status: string } | null> {
    if (!code || code.length < 8) return null;
    const shortHex = code.slice(-8).toLowerCase();
    // Only accept valid hex chars (no hyphens in shortHex)
    if (!/^[0-9a-f]{8}$/.test(shortHex)) return null;

    const rows = await this.prisma.$queryRaw<{ id: string; title: string; status: string }[]>`
      SELECT id, title, status
      FROM projects
      WHERE deleted_at IS NULL
        AND replace(id::text, '-', '') LIKE ${shortHex + '%'}
      LIMIT 1
    `;
    return rows[0] ?? null;
  }

  // ─── Collaborator CRUD ──────────────────────────────────────────────────────

  /** List all collaborators for a project with their user details. */
  async listCollaborators(projectId: string) {
    const rows = await this.prisma.project_collaborators.findMany({
      where: { project_id: projectId },
      include: {
        users: {
          select: {
            id: true,
            email: true,
            primary_phone: true,
            user_profiles: {
              select: { metadata: true },
              take: 1,
            },
          },
        },
      },
      orderBy: { added_at: 'asc' },
    });

    return rows.map((c) => {
      const meta = (c.users.user_profiles?.[0]?.metadata ?? {}) as Record<string, string>;
      return {
        user_id: c.user_id,
        email: c.users.email,
        primary_phone: c.users.primary_phone,
        first_name: meta.first_name ?? null,
        last_name: meta.last_name ?? null,
        role: (c.role ?? 'collaborator') as CollaboratorRole,
        added_at: c.added_at,
        added_by: c.added_by ?? null,
      };
    });
  }

  /** Throw if the requesting user doesn't have a manage-level role on the project. */
  private async assertCanManage(requestingUserId: string, projectId: string) {
    const membership = await this.prisma.project_collaborators.findUnique({
      where: { project_id_user_id: { project_id: projectId, user_id: requestingUserId } },
    });
    const role = (membership?.role ?? null) as CollaboratorRole | null;
    if (!role || !MANAGE_ROLES.includes(role)) {
      throw new ForbiddenException('Only owners and managers can manage collaborators');
    }
    return role;
  }

  /**
   * Add a collaborator by email. Looks up user, then inserts them.
   * Only owners/managers may call this. Defaults to 'collaborator' role.
   */
  async addCollaborator(
    requestingUserId: string,
    projectId: string,
    email: string,
    role: CollaboratorRole = 'collaborator',
  ) {
    await this.assertCanManage(requestingUserId, projectId);

    // Verify project exists
    const project = await this.prisma.projects.findFirst({ where: { id: projectId, deleted_at: null } });
    if (!project) throw new NotFoundException('Project not found');

    // Owners cannot be added via this endpoint (only set on creation)
    if (role === 'owner') throw new ForbiddenException('Cannot assign owner role via this endpoint');

    const target = await this.prisma.users.findUnique({ where: { email } });
    if (!target) throw new NotFoundException(`No user found with email ${email}`);

    // Check if already a member
    const existing = await this.prisma.project_collaborators.findUnique({
      where: { project_id_user_id: { project_id: projectId, user_id: target.id } },
    });
    if (existing) throw new ConflictException('User is already a collaborator on this project');

    await this.prisma.project_collaborators.create({
      data: { project_id: projectId, user_id: target.id, role, added_by: requestingUserId },
    });

    return { user_id: target.id, email: target.email, role };
  }

  /**
   * Update a collaborator's role. Owners may not have their role changed.
   * The requesting user must be owner/manager, and the new role cannot be 'owner'.
   */
  async updateCollaboratorRole(
    requestingUserId: string,
    projectId: string,
    targetUserId: string,
    newRole: CollaboratorRole,
  ) {
    const requesterRole = await this.assertCanManage(requestingUserId, projectId);

    if (newRole === 'owner') throw new ForbiddenException('Cannot assign owner role');

    const target = await this.prisma.project_collaborators.findUnique({
      where: { project_id_user_id: { project_id: projectId, user_id: targetUserId } },
    });
    if (!target) throw new NotFoundException('Collaborator not found');
    if (target.role === 'owner') throw new ForbiddenException('Cannot change the owner\'s role');

    // Managers cannot promote other users to manager (only owners can)
    if (newRole === 'manager' && requesterRole !== 'owner') {
      throw new ForbiddenException('Only the owner can assign manager role');
    }

    await this.prisma.project_collaborators.update({
      where: { project_id_user_id: { project_id: projectId, user_id: targetUserId } },
      data: { role: newRole },
    });

    return { user_id: targetUserId, role: newRole };
  }

  /**
   * Remove a collaborator. Owners cannot be removed. Managers can remove
   * collaborators/viewers, but only owners can remove managers.
   */
  async removeCollaborator(requestingUserId: string, projectId: string, targetUserId: string) {
    const requesterRole = await this.assertCanManage(requestingUserId, projectId);

    if (requestingUserId === targetUserId) {
      throw new ForbiddenException('You cannot remove yourself; transfer ownership first');
    }

    const target = await this.prisma.project_collaborators.findUnique({
      where: { project_id_user_id: { project_id: projectId, user_id: targetUserId } },
    });
    if (!target) throw new NotFoundException('Collaborator not found');
    if (target.role === 'owner') throw new ForbiddenException('Cannot remove the project owner');
    if (target.role === 'manager' && requesterRole !== 'owner') {
      throw new ForbiddenException('Only the owner can remove a manager');
    }

    await this.prisma.project_collaborators.delete({
      where: { project_id_user_id: { project_id: projectId, user_id: targetUserId } },
    });

    return { removed: true, user_id: targetUserId };
  }

  /**
   * Join a project using its join code. Adds the user as a 'collaborator'.
   * Idempotent — if already a member, returns their existing record.
   */
  async joinProject(userId: string, code: string) {
    const project = await this.findByJoinCode(code);
    if (!project) throw new NotFoundException('No project found for that code');

    const existing = await this.prisma.project_collaborators.findUnique({
      where: { project_id_user_id: { project_id: project.id, user_id: userId } },
    });
    if (existing) {
      return { project, role: existing.role ?? 'collaborator', already_member: true };
    }

    const projectRecord = await this.prisma.projects.findUnique({
      where: { id: project.id },
      select: { owner_user_id: true },
    });
    await this.prisma.project_collaborators.create({
      data: {
        project_id: project.id,
        user_id: userId,
        role: 'collaborator',
        added_by: projectRecord?.owner_user_id ?? userId,
      },
    });

    return { project, role: 'collaborator', already_member: false };
  }

  /**
   * Delete a project. Only the owner may delete.
   */
  async deleteProject(userId: string, projectId: string) {
    const membership = await this.prisma.project_collaborators.findUnique({
      where: { project_id_user_id: { project_id: projectId, user_id: userId } },
    });
    if (!membership || membership.role !== 'owner') {
      throw new ForbiddenException('Only the project owner can delete this project');
    }
    await this.prisma.projects.delete({ where: { id: projectId } });
    return { deleted: true };
  }

  /**
   * Get a collaborator's role for the given project (used by other services).
   * Returns null if the user is not a member.
   */
  async getCollaboratorRole(userId: string, projectId: string): Promise<CollaboratorRole | null> {
    const row = await this.prisma.project_collaborators.findUnique({
      where: { project_id_user_id: { project_id: projectId, user_id: userId } },
    });
    return row ? ((row.role ?? 'collaborator') as CollaboratorRole) : null;
  }

  /**
   * Create a project from AI chat intake with full contract data.
   * Creates:
   * - Project record
   * - AI conversation state record (if thread_id provided)
   * - Stores contract data in ai_event_summary
   */
  async createFromAiIntake(
    dto: {
      project_id?: string;
      client_name?: string;
      contact_email?: string;
      contact_phone?: string;
      event_type?: string;
      event_date?: string;
      guest_count?: number;
      service_type?: string;
      menu_items?: string[];
      main_dishes?: string[];
      appetizers?: string[];
      desserts?: string[];
      menu_notes?: string;
      dietary_restrictions?: string[];
      budget_range?: string;
      venue_name?: string;
      venue_address?: string;
      setup_time?: string;
      service_time?: string;
      addons?: string[];
      modifications?: string[];
      thread_id?: string;
      generate_contract?: boolean;
    },
    userId: string,
  ) {
    // Validate menu items against DB — only keep items that exist
    const dbItems = await this.prisma.menu_items.findMany({
      where: { active: true },
      select: { name: true },
    });
    const dbNameSet = new Set(dbItems.map((i) => i.name.toLowerCase()));
    const validateItems = (items: string[]): string[] => {
      if (!items.length) return [];
      return items.filter((item) => {
        const nameLower = item.toLowerCase().replace(/\s*\(.*?\)/g, '').trim();
        return (
          dbNameSet.has(nameLower) ||
          [...dbNameSet].some((db) => db.includes(nameLower) || nameLower.includes(db))
        );
      });
    };

    const validatedMainDishes = validateItems(dto.main_dishes || []);
    const validatedAppetizers = validateItems(dto.appetizers || []);
    const validatedDesserts    = validateItems(dto.desserts || []);
    // Legacy flat array support (menu_items without categorization)
    const validatedMenuItems = dto.main_dishes
      ? [...validatedMainDishes, ...validatedAppetizers, ...validatedDesserts]
      : validateItems(dto.menu_items || []);

    const result = await this.prisma.$transaction(async (tx) => {
      const projectTitle = dto.event_type && dto.client_name
        ? `${dto.event_type} - ${dto.client_name}`
        : dto.client_name || dto.event_type || 'AI Intake (draft)';

      // Resolve project_id: explicit > lookup by thread_id > create new
      let resolvedProjectId = dto.project_id;
      if (!resolvedProjectId && dto.thread_id) {
        const convState = await tx.ai_conversation_states.findUnique({
          where: { thread_id: dto.thread_id },
          select: { project_id: true },
        });
        if (convState?.project_id) resolvedProjectId = convState.project_id;
      }

      let project;
      if (resolvedProjectId) {
        project = await tx.projects.update({
          where: { id: resolvedProjectId },
          data: {
            title: projectTitle,
            event_date: dto.event_date ? new Date(dto.event_date) : undefined,
            guest_count: dto.guest_count ?? undefined,
            ai_event_summary: JSON.stringify(dto),
          },
        });
      } else {
        project = await tx.projects.create({
          data: {
            owner_user_id: userId,
            title: projectTitle,
            event_date: dto.event_date ? new Date(dto.event_date) : null,
            guest_count: dto.guest_count ?? null,
            status: 'draft',
            created_via_ai_intake: true,
            ai_event_summary: JSON.stringify(dto),
          },
        });

        // Add owner as collaborator only on initial creation
        await tx.project_collaborators.create({
          data: { project_id: project.id, user_id: userId, role: 'owner', added_by: userId },
        });
      }

      // Create venue if provided and doesn't exist
      let venue = null;
      if (dto.venue_name) {
        venue = await tx.venues.findFirst({
          where: { name: dto.venue_name },
        });

        if (!venue) {
          venue = await tx.venues.create({
            data: {
              name: dto.venue_name,
              address: dto.venue_address || '',
            },
          });
        }

        // Link venue to project
        await tx.projects.update({
          where: { id: project.id },
          data: { venue_id: venue.id },
        });
      }

      // Generate contract if requested
      let contract = null;
      if (dto.generate_contract) {
        console.log(`📝 [Contract] Generating contract for project ${project.id}`);
        console.log(`👤 [Contract] Client: ${dto.client_name} (${dto.contact_email})`);
        console.log(`📅 [Contract] Event: ${dto.event_type} on ${dto.event_date}`);
        console.log(`👥 [Contract] Guest count: ${dto.guest_count}`);

        // Create contract with AI-generated data
        // Status: pending_staff_approval - needs staff review before sending to client
        contract = await tx.contracts.create({
          data: {
            project_id: project.id,
            contract_group_id: project.id, // Use project ID as contract group ID (valid UUID)
            version_number: 1,
            status: 'pending_staff_approval', // ✅ Changed from 'draft'
            title: `Contract - ${dto.event_type || 'Event'} for ${dto.client_name || 'Client'}`,
            body: {
              client_info: {
                name: dto.client_name,
                email: dto.contact_email,
                phone: dto.contact_phone,
              },
              event_details: {
                type: dto.event_type,
                date: dto.event_date,
                guest_count: dto.guest_count,
                service_type: dto.service_type,
                venue: {
                  name: dto.venue_name,
                  address: dto.venue_address,
                },
              },
              menu: {
                items: validatedMenuItems,
                main_dishes: validatedMainDishes,
                appetizers: validatedAppetizers,
                desserts: validatedDesserts,
                dietary_restrictions: dto.dietary_restrictions || [],
                notes: dto.menu_notes || undefined,
              },
              logistics: {
                setup_time: dto.setup_time,
                service_time: dto.service_time,
              },
              additional: {
                addons: dto.addons || [],
                modifications: dto.modifications || [],
                budget_range: dto.budget_range,
              },
            },
            is_active: true,
            created_by: userId,
          },
        });

        console.log(`✅ [Contract] Contract created with ID: ${contract.id}`);
        console.log(`📋 [Contract] Status: pending_staff_approval - Awaiting staff review`);
      }

      // Note: All contract data is stored in ai_event_summary JSON field
      // The events table is for audit logs, not catering event details

      return {
        project,
        venue,
        contract,
        contract_data: dto,
      };
    });

    // Enqueue PDF generation if contract was created
    // NOTE: Contract is NOT sent to SignWell yet - awaiting staff approval
    if (result.contract) {
      console.log(`📄 [Contract] Enqueuing PDF generation for contract ${result.contract.id}`);

      await this.contractsService.enqueuePdfGeneration(
        result.contract.id,
        userId,
      );

      console.log(`✅ [Contract] Contract ${result.contract.id} created and queued for PDF generation`);
      console.log(`⏳ [Contract] Status: ${result.contract.status} - Awaiting staff approval`);
      console.log(`📧 [Contract] Client email: ${dto.contact_email}`);
    }

    console.log(`✅ [Project] Project ${result.project.id} created successfully`);
    console.log(`📊 [Project] Event type: ${dto.event_type}, Guest count: ${dto.guest_count}`);

    return result;
  }
}
