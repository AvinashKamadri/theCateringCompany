import { Module, forwardRef } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { SignWellService } from './signwell.service';
import { SignWellController } from './signwell.controller';
import { ContractsModule } from '../contracts/contracts.module';

@Module({
  imports: [
    ConfigModule,
    forwardRef(() => ContractsModule),
  ],
  controllers: [SignWellController],
  providers: [SignWellService],
  exports: [SignWellService],
})
export class SignWellModule {}
