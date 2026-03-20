import {
  Controller,
  Get,
  Post,
  Patch,
  Delete,
  Param,
  Body,
  UseGuards,
  HttpCode,
  HttpStatus,
} from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { ProjectsService, CollaboratorRole } from './projects.service';
import { CurrentUser } from '../common/decorators/current-user.decorator';

@UseGuards(AuthGuard('jwt'))
@Controller('projects')
export class ProjectsController {
  constructor(private readonly projectsService: ProjectsService) {}

  /**
   * GET /projects
   * List all projects accessible by the current user.
   */
  @Get()
  async findAll(@CurrentUser() user: { userId: string }) {
    return this.projectsService.findAllForUser(user.userId);
  }

  // ─── Literal routes must come BEFORE :id to avoid param collision ───────────

  /**
   * GET /projects/by-code/:code
   * Preview a project's name/status from a join code (no join yet).
   */
  @Get('by-code/:code')
  async lookupByCode(@Param('code') code: string) {
    const project = await this.projectsService.findByJoinCode(code);
    if (!project) {
      return { found: false };
    }
    return {
      found: true,
      project: {
        id: project.id,
        title: project.title,
        status: project.status,
      },
    };
  }

  /**
   * POST /projects/join
   * Join an existing project using its join code.
   * Adds the authenticated user as a 'collaborator'.
   */
  @Post('join')
  async joinByCode(
    @CurrentUser() user: { userId: string },
    @Body() body: { code: string },
  ) {
    return this.projectsService.joinProject(user.userId, body.code);
  }

  // ─── :id routes ─────────────────────────────────────────────────────────────

  /**
   * GET /projects/:id
   * Get a single project by ID, including the latest active contract.
   */
  @Get(':id')
  async findOne(
    @Param('id') id: string,
    @CurrentUser() user: { userId: string },
  ) {
    return this.projectsService.findById(id);
  }

  /**
   * GET /projects/:id/collaborators
   * List all collaborators on a project with their roles.
   */
  @Get(':id/collaborators')
  async listCollaborators(@Param('id') projectId: string) {
    const collaborators = await this.projectsService.listCollaborators(projectId);
    return { collaborators };
  }

  /**
   * POST /projects/:id/collaborators
   * Add a collaborator by email. Role defaults to 'collaborator'.
   * Only owners/managers may call this.
   */
  @Post(':id/collaborators')
  async addCollaborator(
    @Param('id') projectId: string,
    @CurrentUser() user: { userId: string },
    @Body() body: { email: string; role?: CollaboratorRole },
  ) {
    return this.projectsService.addCollaborator(
      user.userId,
      projectId,
      body.email,
      body.role,
    );
  }

  /**
   * PATCH /projects/:id/collaborators/:userId
   * Update a collaborator's role. Only owners/managers may call this.
   */
  @Patch(':id/collaborators/:userId')
  async updateCollaboratorRole(
    @Param('id') projectId: string,
    @Param('userId') targetUserId: string,
    @CurrentUser() user: { userId: string },
    @Body() body: { role: CollaboratorRole },
  ) {
    return this.projectsService.updateCollaboratorRole(
      user.userId,
      projectId,
      targetUserId,
      body.role,
    );
  }

  /**
   * DELETE /projects/:id
   * Delete a project. Only the owner may delete.
   */
  @Delete(':id')
  @HttpCode(HttpStatus.OK)
  async deleteProject(
    @Param('id') projectId: string,
    @CurrentUser() user: { userId: string },
  ) {
    return this.projectsService.deleteProject(user.userId, projectId);
  }

  /**
   * DELETE /projects/:id/collaborators/:userId
   * Remove a collaborator. Only owners/managers may call this.
   */
  @Delete(':id/collaborators/:userId')
  @HttpCode(HttpStatus.OK)
  async removeCollaborator(
    @Param('id') projectId: string,
    @Param('userId') targetUserId: string,
    @CurrentUser() user: { userId: string },
  ) {
    return this.projectsService.removeCollaborator(user.userId, projectId, targetUserId);
  }

  /**
   * GET /projects/:id/join-code
   * Get the join code for a project. Only accessible by members.
   */
  @Get(':id/join-code')
  async getJoinCode(
    @Param('id') projectId: string,
    @CurrentUser() user: { userId: string },
  ) {
    const project = await this.projectsService.findById(projectId);
    const role = await this.projectsService.getCollaboratorRole(user.userId, projectId);
    if (!role) {
      return { error: 'Not a member of this project' };
    }
    return {
      join_code: this.projectsService.generateJoinCode({ id: projectId, title: project.title }),
    };
  }

  /**
   * POST /projects
   * Create a new project. Sets owner_user_id to the current user
   * and inserts the user into project_collaborators.
   */
  @Post()
  async create(
    @CurrentUser() user: { userId: string },
    @Body()
    body: {
      title: string;
      eventDate?: string;
      eventEndDate?: string;
      guestCount?: number;
    },
  ) {
    return this.projectsService.create(user.userId, body);
  }

  /**
   * POST /projects/ai-intake
   * Create a new project from AI chat intake with contract data.
   * Requires authentication - associates project with authenticated user.
   * Can handle partial data (not all fields required).
   * If generate_contract=true, creates contract and PDF immediately.
   */
  @Post('ai-intake')
  async createFromAiIntake(
    @CurrentUser() user: { userId: string },
    @Body()
    body: {
      project_id?: string;
      // Contract data from AI (all fields optional for partial intake)
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
      // Flag to generate contract immediately
      generate_contract?: boolean;
    },
  ) {
    try {
      console.log('🎯 [API] Creating project from AI intake for user:', user.userId);
      console.log('📦 [API] Request body:', JSON.stringify(body, null, 2));

      const result = await this.projectsService.createFromAiIntake(body, user.userId);

      console.log('✅ [API] Project created successfully:', result.project.id);
      console.log('📋 [API] Contract created:', result.contract?.id || 'No contract');
      console.log('📤 [API] Returning result:', JSON.stringify({
        project: { id: result.project.id, title: result.project.title },
        contract: result.contract ? { id: result.contract.id, status: result.contract.status } : null,
        venue: result.venue ? { id: result.venue.id, name: result.venue.name } : null,
      }, null, 2));

      return result;
    } catch (error) {
      console.error('❌ [API] Error creating project from AI intake:', error);
      console.error('❌ [API] Error stack:', error.stack);
      console.error('❌ [API] Error message:', error.message);
      throw error;
    }
  }
}
