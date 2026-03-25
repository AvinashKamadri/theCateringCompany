import {
  Controller,
  Post,
  Get,
  Body,
  Req,
  Res,
  UseGuards,
  HttpCode,
  HttpStatus,
  UnauthorizedException,
} from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { Request, Response } from 'express';
import { AuthService } from './auth.service';
import { Public } from '../common/decorators/public.decorator';

@Controller('auth')
export class AuthController {
  constructor(private readonly authService: AuthService) {}

  @Public()
  @Post('signup')
  async signup(
    @Body()
    body: {
      email: string;
      password: string;
      primary_phone?: string;
      first_name?: string;
      last_name?: string;
      /** Optional join code to auto-add to an existing project on signup */
      project_code?: string;
    },
    @Res({ passthrough: true }) res: Response,
  ) {
    const { user, accessToken, refreshToken, joinedProject } =
      await this.authService.signup(
        body.email,
        body.password,
        {
          primary_phone: body.primary_phone,
          first_name: body.first_name,
          last_name: body.last_name,
        },
        body.project_code,
      );

    this.setAccessTokenCookie(res, accessToken);
    this.setRefreshTokenCookie(res, refreshToken);

    return {
      user: {
        id: user.id,
        email: user.email,
        primary_phone: user.primary_phone,
        status: user.status,
        role: user.email.endsWith('@catering-company.com') ? 'staff' : 'host',
        created_at: user.created_at,
        updated_at: user.updated_at,
      },
      joined_project: joinedProject ?? null,
      accessToken,
    };
  }

  @Public()
  @Post('login')
  @HttpCode(HttpStatus.OK)
  async login(
    @Body() body: { email: string; password: string },
    @Res({ passthrough: true }) res: Response,
  ) {
    const { user, accessToken, refreshToken } =
      await this.authService.login(body.email, body.password);

    this.setAccessTokenCookie(res, accessToken);
    this.setRefreshTokenCookie(res, refreshToken);

    return {
      user: {
        id: user.id,
        email: user.email,
        primary_phone: user.primary_phone,
        status: user.status,
        role: user.email.endsWith('@catering-company.com') ? 'staff' : 'host',
        created_at: user.created_at,
        updated_at: user.updated_at,
      },
      accessToken,
    };
  }

  @UseGuards(AuthGuard('jwt'))
  @Post('logout')
  @HttpCode(HttpStatus.OK)
  async logout(
    @Req() req: Request,
    @Res({ passthrough: true }) res: Response,
  ) {
    const user = req.user as { userId: string; sessionId: string; email: string };
    await this.authService.logout(user.sessionId);

    res.clearCookie('app_jwt', { path: '/' });
    res.clearCookie('refresh_token', { path: '/' });

    return { message: 'Logged out successfully' };
  }

  @Public()
  @Post('refresh')
  @HttpCode(HttpStatus.OK)
  async refresh(
    @Req() req: Request,
    @Res({ passthrough: true }) res: Response,
  ) {
    const refreshTokenValue = req.cookies?.['refresh_token'];
    if (!refreshTokenValue) {
      throw new UnauthorizedException('No refresh token provided');
    }

    const { accessToken, refreshToken } =
      await this.authService.refresh(refreshTokenValue);

    this.setAccessTokenCookie(res, accessToken);
    this.setRefreshTokenCookie(res, refreshToken);

    return { message: 'Tokens refreshed successfully', accessToken };
  }

  @UseGuards(AuthGuard('jwt'))
  @Get('me')
  async me(@Req() req: Request) {
    const user = req.user as { userId: string; sessionId: string; email: string };
    const dbUser = await this.authService.validateUser(user.userId);
    if (!dbUser) {
      throw new UnauthorizedException('User not found');
    }
    return {
      user: {
        id: dbUser.id,
        email: dbUser.email,
        primary_phone: dbUser.primary_phone,
        status: dbUser.status,
        role: dbUser.email.endsWith('@catering-company.com') ? 'staff' : 'host',
        created_at: dbUser.created_at,
        updated_at: dbUser.updated_at,
      },
    };
  }

  private setAccessTokenCookie(res: Response, token: string): void {
    res.cookie('app_jwt', token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      path: '/',
      maxAge: 2 * 60 * 60 * 1000, // 2 hours (was 15 minutes)
    });
  }

  private setRefreshTokenCookie(res: Response, token: string): void {
    res.cookie('refresh_token', token, {
      httpOnly: true,
      secure: true,
      sameSite: 'none',
      path: '/',
      maxAge: 7 * 24 * 60 * 60 * 1000,
    });
  }
}
