import {
  WebSocketGateway,
  WebSocketServer,
  OnGatewayConnection,
  OnGatewayDisconnect,
  SubscribeMessage,
  MessageBody,
  ConnectedSocket,
} from '@nestjs/websockets';
import { Server, Socket } from 'socket.io';
import { JwtService } from '@nestjs/jwt';
import { PrismaService } from '../prisma.service';

@WebSocketGateway({
  cors: {
    origin: process.env.CORS_ORIGIN || 'http://localhost:3000',
    credentials: true,
  },
})
export class SocketsGateway implements OnGatewayConnection, OnGatewayDisconnect {
  @WebSocketServer()
  server: Server;

  constructor(
    private jwtService: JwtService,
    private prisma: PrismaService,
  ) {}

  async handleConnection(client: Socket) {
    try {
      // Extract JWT from auth token (cross-origin) or cookie fallback
      let token: string | undefined = client.handshake.auth?.token;

      if (!token) {
        const cookies = client.handshake.headers.cookie;
        const tokenMatch = cookies?.split(';').find(c => c.trim().startsWith('app_jwt='));
        token = tokenMatch?.split('=')[1]?.trim();
      }

      if (!token) {
        client.disconnect();
        return;
      }
      const payload = this.jwtService.verify(token);
      const userId = payload.sub;

      // Store user info on socket
      client.data.user = { userId, email: payload.email, sessionId: payload.sessionId };

      // Join user-specific room
      client.join(`user:${userId}`);

      // Load project memberships and join project rooms
      const memberships = await this.prisma.project_collaborators.findMany({
        where: { user_id: userId },
        select: { project_id: true },
      });

      for (const m of memberships) {
        client.join(`project:${m.project_id}`);
      }
    } catch (error) {
      client.disconnect();
    }
  }

  handleDisconnect(client: Socket) {
    // Cleanup handled automatically by socket.io room management
  }

  @SubscribeMessage('thread:join')
  handleJoinThread(@ConnectedSocket() client: Socket, @MessageBody() data: { threadId: string }) {
    if (client.data.user) {
      client.join(`thread:${data.threadId}`);
    }
  }

  @SubscribeMessage('thread:leave')
  handleLeaveThread(@ConnectedSocket() client: Socket, @MessageBody() data: { threadId: string }) {
    client.leave(`thread:${data.threadId}`);
  }

  @SubscribeMessage('message.typing')
  handleTyping(@ConnectedSocket() client: Socket, @MessageBody() data: { threadId: string }) {
    if (client.data.user) {
      client.to(`thread:${data.threadId}`).emit('message.typing', {
        userId: client.data.user.userId,
        threadId: data.threadId,
      });
    }
  }

  // Public methods for other modules to emit events
  emitToRoom(room: string, event: string, data: any) {
    this.server.to(room).emit(event, data);
  }

  emitToUser(userId: string, event: string, data: any) {
    this.server.to(`user:${userId}`).emit(event, data);
  }
}
