import { Request, Response } from 'express';
import { AuthService } from './auth.service';
export declare class AuthController {
    private readonly authService;
    constructor(authService: AuthService);
    signup(body: {
        email: string;
        password: string;
        primary_phone?: string;
        first_name?: string;
        last_name?: string;
    }, res: Response): Promise<{
        user: {
            id: any;
            email: any;
            primary_phone: any;
            status: any;
            created_at: any;
            updated_at: any;
        };
    }>;
    login(body: {
        email: string;
        password: string;
    }, res: Response): Promise<{
        user: {
            id: any;
            email: any;
            primary_phone: any;
            status: any;
            created_at: any;
            updated_at: any;
        };
    }>;
    logout(req: Request, res: Response): Promise<{
        message: string;
    }>;
    refresh(req: Request, res: Response): Promise<{
        message: string;
    }>;
    me(req: Request): Promise<{
        user: {
            id: string;
            email: string;
            primary_phone: string | null;
            status: string;
            created_at: Date;
            updated_at: Date;
        };
    }>;
    private setAccessTokenCookie;
    private setRefreshTokenCookie;
}
