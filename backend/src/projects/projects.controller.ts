import {
  Controller,
  Get,
  Post,
  Param,
  Body,
  UseGuards,
} from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { ProjectsService } from './projects.service';
import { CurrentUser } from '../common/decorators/current-user.decorator';
import { Public } from '../common/decorators/public.decorator';

@UseGuards(AuthGuard('jwt'))
@Controller('projects')
export class ProjectsController {
  constructor(private readonly projectsService: ProjectsService) {}

  /**
   * GET /projects
   * List all projects accessible by the current user
   * (where user is owner_user_id OR in project_collaborators).
   */
  @Get()
  async findAll(@CurrentUser() user: { userId: string }) {
    return this.projectsService.findAllForUser(user.userId);
  }

  /**
   * GET /projects/:id
   * Get a single project by ID, including signed_contract_id
   * and the latest active contract metadata.
   */
  @Get(':id')
  async findOne(
    @Param('id') id: string,
    @CurrentUser() user: { userId: string },
  ) {
    return this.projectsService.findById(id);
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
