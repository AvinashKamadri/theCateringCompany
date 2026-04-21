import {
  Controller,
  Get,
  Post,
  Query,
  Req,
  Res,
  HttpCode,
  HttpStatus,
} from '@nestjs/common';
import { Request, Response } from 'express';
import { Public } from '../common/decorators/public.decorator';
import { GmailService } from './gmail.service';

@Controller('gmail')
export class GmailController {
  constructor(private readonly gmailService: GmailService) {}

  // Initiates Gmail OAuth — user must be logged in (JWT guard applies)
  @Get('auth')
  getAuthUrl(@Req() req: Request) {
    const userId: string = (req as any).user?.userId;
    const url = this.gmailService.getAuthUrl(userId);
    return { url };
  }

  // Google redirects here after consent — no JWT (state param carries userId)
  @Public()
  @Get('callback')
  async handleCallback(
    @Query('code') code: string,
    @Query('state') state: string,
    @Res() res: Response,
  ) {
    await this.gmailService.handleCallback(code, state);
    // Redirect back to settings or dashboard after successful connect
    return res.redirect('/dashboard?gmail=connected');
  }

  // Called on chat open to sync last 10-15 min emails synchronously (~500ms)
  @Post('sync/quick')
  @HttpCode(HttpStatus.OK)
  async quickSync(@Req() req: Request) {
    const userId: string = (req as any).user?.userId;
    const result = await this.gmailService.triggerQuickSync(userId);
    return result;
  }

  @Get('status')
  async getStatus(@Req() req: Request) {
    const userId: string = (req as any).user?.userId;
    const connected = await this.gmailService.isConnected(userId);
    return { connected };
  }
}
