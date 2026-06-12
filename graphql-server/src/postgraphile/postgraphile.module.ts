import { Global, Module } from '@nestjs/common';
import { PostGraphileService } from './postgraphile.service';

@Global()
@Module({
  providers: [PostGraphileService],
  exports: [PostGraphileService],
})
export class PostGraphileModule {}
