import { Module } from '@nestjs/common';
import { JwtModule } from '@nestjs/jwt';
import { SocketsGateway } from './sockets.gateway';
import { PrismaService } from '../prisma.service';

@Module({
  imports: [JwtModule],
  providers: [SocketsGateway, PrismaService],
  exports: [SocketsGateway],
})
export class SocketsModule {}
