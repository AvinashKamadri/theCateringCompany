import { Injectable, NotFoundException, Inject, forwardRef } from '@nestjs/common';
import { PrismaService } from '../prisma.service';
import { ContractsService } from '../contracts/contracts.service';

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
  async findAllForUser(userId: string) {
    const projects = await this.prisma.projects.findMany({
      where: {
        deleted_at: null,
        OR: [
          { owner_user_id: userId },
          {
            project_collaborators: {
              some: { user_id: userId },
            },
          },
        ],
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
        },
      });

      return project;
    });
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
      client_name?: string;
      contact_email?: string;
      contact_phone?: string;
      event_type?: string;
      event_date?: string;
      guest_count?: number;
      service_type?: string;
      menu_items?: string[];
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
    const result = await this.prisma.$transaction(async (tx) => {
      // Create project with AI data (handle partial/missing fields)
      const project = await tx.projects.create({
        data: {
          // Associate with authenticated user
          owner_user_id: userId,
          title: dto.event_type && dto.client_name
            ? `${dto.event_type} - ${dto.client_name}`
            : dto.client_name || dto.event_type || 'AI Generated Event',
          event_date: dto.event_date ? new Date(dto.event_date) : null,
          guest_count: dto.guest_count ?? null,
          status: 'draft',
          created_via_ai_intake: true,
          ai_event_summary: JSON.stringify(dto),
        },
      });

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

      // Add owner as collaborator
      await tx.project_collaborators.create({
        data: {
          project_id: project.id,
          user_id: userId,
        },
      });

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
                items: dto.menu_items || [],
                dietary_restrictions: dto.dietary_restrictions || [],
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
