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
   * Create a new project from AI chat intake with full contract data.
   * Public endpoint - no authentication required.
   */
  @Public()
  @Post('ai-intake')
  async createFromAiIntake(
    @Body()
    body: {
      // Contract data from AI
      client_name: string;
      contact_email: string;
      contact_phone: string;
      event_type: string;
      event_date: string;
      guest_count: number;
      service_type: string;
      menu_items: string[];
      dietary_restrictions: string[];
      budget_range: string;
      venue_name: string;
      venue_address: string;
      setup_time: string;
      service_time: string;
      addons: string[];
      modifications: string[];
      // Optional fields
      thread_id?: string;
    },
  ) {
    return this.projectsService.createFromAiIntake(body);
  }
}
