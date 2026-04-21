import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { GmailController } from './gmail.controller';
import { GmailService } from './gmail.service';
import { PrismaService } from '../prisma.service';

@Module({
  imports: [ConfigModule],
  controllers: [GmailController],
  providers: [GmailService, PrismaService],
  exports: [GmailService],
})
export class GmailModule {}