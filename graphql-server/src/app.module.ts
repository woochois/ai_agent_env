import { Module } from '@nestjs/common';

// TODO: Task 2.2 - Import PostGraphileModule
// import { PostGraphileModule } from './postgraphile/postgraphile.module';

// TODO: Task 3 - Import AuthModule
// import { AuthModule } from './features/auth/auth.module';

@Module({
  imports: [
    // PostGraphileModule,  // Task 2.2: PostGraphile DB connection + GraphQL schema
    // AuthModule,          // Task 3: JWT authentication (login, refresh, logout)
  ],
  controllers: [],
  providers: [],
})
export class AppModule {}
