import { Strategy } from 'passport-jwt';
import { ConfigService } from '@nestjs/config';
import { AuthService } from './auth.service';
declare const JwtStrategy_base: new (...args: any[]) => Strategy;
export declare class JwtStrategy extends JwtStrategy_base {
    private readonly configService;
    private readonly authService;
    constructor(configService: ConfigService, authService: AuthService);
    validate(payload: {
        sub: string;
        sessionId: string;
        email: string;
    }): Promise<{
        userId: string;
        sessionId: string;
        email: string;
    }>;
}
export {};
