import { JwtService } from '@nestjs/jwt';
import { PrismaService } from '../prisma.service';
export declare class AuthService {
    private readonly prisma;
    private readonly jwtService;
    constructor(prisma: PrismaService, jwtService: JwtService);
    signup(email: string, password: string, profile?: {
        primary_phone?: string;
        first_name?: string;
        last_name?: string;
    }): Promise<{
        user: any;
        accessToken: string;
        refreshToken: string;
    }>;
    login(email: string, password: string): Promise<{
        user: any;
        accessToken: string;
        refreshToken: string;
    }>;
    logout(sessionId: string): Promise<void>;
    refresh(refreshTokenValue: string): Promise<{
        accessToken: string;
        refreshToken: string;
    }>;
    validateUser(userId: string): Promise<{
        id: string;
        email: string;
        password_hash: string | null;
        primary_phone: string | null;
        status: string;
        created_at: Date;
        updated_at: Date;
        deleted_at: Date | null;
        deleted_by: string | null;
    } | null>;
    generateTokens(userId: string, sessionId: string, email: string): Promise<{
        accessToken: string;
        refreshToken: string;
    }>;
    private createSessionAndTokens;
}
