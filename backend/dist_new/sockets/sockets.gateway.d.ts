import { OnGatewayConnection, OnGatewayDisconnect } from '@nestjs/websockets';
import { Server, Socket } from 'socket.io';
import { JwtService } from '@nestjs/jwt';
import { PrismaService } from '../prisma.service';
export declare class SocketsGateway implements OnGatewayConnection, OnGatewayDisconnect {
    private jwtService;
    private prisma;
    server: Server;
    constructor(jwtService: JwtService, prisma: PrismaService);
    handleConnection(client: Socket): Promise<void>;
    handleDisconnect(client: Socket): void;
    handleJoinThread(client: Socket, data: {
        threadId: string;
    }): void;
    handleLeaveThread(client: Socket, data: {
        threadId: string;
    }): void;
    handleTyping(client: Socket, data: {
        threadId: string;
    }): void;
    emitToRoom(room: string, event: string, data: any): void;
    emitToUser(userId: string, event: string, data: any): void;
}
