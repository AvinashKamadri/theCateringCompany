import { Controller, Get, UseGuards } from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { CrmService } from './crm.service';
import { CurrentUser } from '../common/decorators/current-user.decorator';

@Controller('crm')
@UseGuards(AuthGuard('jwt'))
export class CrmController {
  constructor(private readonly crmService: CrmService) {}

  @Get('leads')
  getLeads(@CurrentUser() user: { userId: string; email: string }) {
    return this.crmService.getLeads(user.email);
  }

  @Get('stats')
  getStats(@CurrentUser() user: { userId: string; email: string }) {
    return this.crmService.getStats(user.email);
  }

  @Get('analytics')
  getAnalytics(@CurrentUser() user: { userId: string; email: string }) {
    return this.crmService.getAnalytics(user.email);
  }
}
