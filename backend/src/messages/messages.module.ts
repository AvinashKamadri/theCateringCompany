import { Module } from '@nestjs/common';
import { BullModule } from '@nestjs/bullmq';
import { MessagesController } from './messages.controller';
import { MessagesService } from './messages.service';
import { PrismaService } from '../prisma.service';
import { SocketsModule } from '../sockets/sockets.module';

@Module({
  imports: [
    BullModule.registerQueue({ name: 'vector_indexing' }),
    SocketsModule,
  ],
  controllers: [MessagesController],
  providers: [MessagesService, PrismaService],
  exports: [MessagesService],
})
export class MessagesModule {}
