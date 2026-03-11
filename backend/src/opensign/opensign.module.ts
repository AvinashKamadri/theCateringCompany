import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { OpenSignService } from './opensign.service';
import { OpenSignController } from './opensign.controller';

@Module({
  imports: [ConfigModule],
  providers: [OpenSignService],
  controllers: [OpenSignController],
  exports: [OpenSignService],
})
export class OpenSignModule {}
