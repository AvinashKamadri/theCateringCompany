"use strict";
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};
var __param = (this && this.__param) || function (paramIndex, decorator) {
    return function (target, key) { decorator(target, key, paramIndex); }
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.SocketsGateway = void 0;
const websockets_1 = require("@nestjs/websockets");
const socket_io_1 = require("socket.io");
const jwt_1 = require("@nestjs/jwt");
const prisma_service_1 = require("../prisma.service");
let SocketsGateway = class SocketsGateway {
    constructor(jwtService, prisma) {
        this.jwtService = jwtService;
        this.prisma = prisma;
    }
    async handleConnection(client) {
        try {
            const cookies = client.handshake.headers.cookie;
            if (!cookies) {
                client.disconnect();
                return;
            }
            const tokenMatch = cookies.split(';').find(c => c.trim().startsWith('app_jwt='));
            if (!tokenMatch) {
                client.disconnect();
                return;
            }
            const token = tokenMatch.split('=')[1]?.trim();
            const payload = this.jwtService.verify(token);
            const userId = payload.sub;
            client.data.user = { userId, email: payload.email, sessionId: payload.sessionId };
            client.join(`user:${userId}`);
            const memberships = await this.prisma.project_collaborators.findMany({
                where: { user_id: userId },
                select: { project_id: true },
            });
            for (const m of memberships) {
                client.join(`project:${m.project_id}`);
            }
        }
        catch (error) {
            client.disconnect();
        }
    }
    handleDisconnect(client) {
    }
    handleJoinThread(client, data) {
        if (client.data.user) {
            client.join(`thread:${data.threadId}`);
        }
    }
    handleLeaveThread(client, data) {
        client.leave(`thread:${data.threadId}`);
    }
    handleTyping(client, data) {
        if (client.data.user) {
            client.to(`thread:${data.threadId}`).emit('message.typing', {
                userId: client.data.user.userId,
                threadId: data.threadId,
            });
        }
    }
    emitToRoom(room, event, data) {
        this.server.to(room).emit(event, data);
    }
    emitToUser(userId, event, data) {
        this.server.to(`user:${userId}`).emit(event, data);
    }
};
exports.SocketsGateway = SocketsGateway;
__decorate([
    (0, websockets_1.WebSocketServer)(),
    __metadata("design:type", socket_io_1.Server)
], SocketsGateway.prototype, "server", void 0);
__decorate([
    (0, websockets_1.SubscribeMessage)('thread:join'),
    __param(0, (0, websockets_1.ConnectedSocket)()),
    __param(1, (0, websockets_1.MessageBody)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [socket_io_1.Socket, Object]),
    __metadata("design:returntype", void 0)
], SocketsGateway.prototype, "handleJoinThread", null);
__decorate([
    (0, websockets_1.SubscribeMessage)('thread:leave'),
    __param(0, (0, websockets_1.ConnectedSocket)()),
    __param(1, (0, websockets_1.MessageBody)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [socket_io_1.Socket, Object]),
    __metadata("design:returntype", void 0)
], SocketsGateway.prototype, "handleLeaveThread", null);
__decorate([
    (0, websockets_1.SubscribeMessage)('message.typing'),
    __param(0, (0, websockets_1.ConnectedSocket)()),
    __param(1, (0, websockets_1.MessageBody)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [socket_io_1.Socket, Object]),
    __metadata("design:returntype", void 0)
], SocketsGateway.prototype, "handleTyping", null);
exports.SocketsGateway = SocketsGateway = __decorate([
    (0, websockets_1.WebSocketGateway)({
        cors: {
            origin: process.env.CORS_ORIGIN || 'http://localhost:3000',
            credentials: true,
        },
    }),
    __metadata("design:paramtypes", [jwt_1.JwtService,
        prisma_service_1.PrismaService])
], SocketsGateway);
//# sourceMappingURL=sockets.gateway.js.map