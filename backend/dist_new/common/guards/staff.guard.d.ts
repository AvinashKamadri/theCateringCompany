import { CanActivate, ExecutionContext } from '@nestjs/common';
import { Reflector } from '@nestjs/core';
export declare class StaffGuard implements CanActivate {
    private reflector;
    private readonly logger;
    private readonly allowedDomains;
    constructor(reflector: Reflector);
    canActivate(context: ExecutionContext): boolean;
}
