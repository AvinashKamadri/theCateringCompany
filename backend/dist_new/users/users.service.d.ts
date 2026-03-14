import { PrismaService } from '../prisma.service';
export declare class UsersService {
    private prisma;
    constructor(prisma: PrismaService);
    findById(id: string): Promise<{
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
}
