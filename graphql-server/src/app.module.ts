import { Module, MiddlewareConsumer, NestModule, RequestMethod } from '@nestjs/common';
import { PostGraphileModule } from './postgraphile/postgraphile.module';
import { AuthModule } from './features/auth/auth.module';
import { AuthMiddleware } from './features/auth/auth.middleware';

@Module({
  imports: [
    PostGraphileModule, // Task 2.2: PostGraphile DB connection + GraphQL schema
    AuthModule, // Task 3: JWT authentication (login, refresh, logout)
  ],
  controllers: [],
  providers: [],
})
export class AppModule implements NestModule {
  configure(consumer: MiddlewareConsumer): void {
    consumer
      .apply(AuthMiddleware)
      .forRoutes(
        { path: 'graphql', method: RequestMethod.ALL },
      );
  }
}
