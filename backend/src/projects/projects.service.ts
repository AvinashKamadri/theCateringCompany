import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../prisma.service';

@Injectable()
export class ProjectsService {
  constructor(private readonly prisma: PrismaService) {}

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
}
