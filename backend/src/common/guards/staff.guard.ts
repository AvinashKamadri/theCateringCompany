import { Injectable, CanActivate, ExecutionContext, ForbiddenException, Logger } from '@nestjs/common';
import { Reflector } from '@nestjs/core';

@Injectable()
export class StaffGuard implements CanActivate {
  private readonly logger = new Logger(StaffGuard.name);
  private readonly allowedDomains = ['@catering-company.com'];

  constructor(private reflector: Reflector) {}

  canActivate(context: ExecutionContext): boolean {
    const request = context.switchToHttp().getRequest();
    const user = request.user;

    if (!user || !user.email) {
      this.logger.warn(`🚫 [Staff Guard] Access denied - No user or email found`);
      throw new ForbiddenException('Authentication required');
    }

    // Check if email ends with allowed domains
    const isStaff = this.allowedDomains.some(domain =>
      user.email.toLowerCase().endsWith(domain.toLowerCase())
    );

    if (!isStaff) {
      this.logger.warn(`🚫 [Staff Guard] Access denied - ${user.email} is not a staff member`);
      this.logger.warn(`🚫 [Staff Guard] Allowed domains: ${this.allowedDomains.join(', ')}`);
      throw new ForbiddenException('Staff access required. Only @catering-company.com accounts can access this resource.');
    }

    this.logger.log(`✅ [Staff Guard] Access granted - ${user.email} is staff`);
    return true;
  }
}
