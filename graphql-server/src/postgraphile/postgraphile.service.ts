import { Injectable, OnModuleInit, Logger } from '@nestjs/common';
import { HttpAdapterHost } from '@nestjs/core';
import { postgraphile, PostGraphileOptions } from 'postgraphile';
import { Pool } from 'pg';
import { IncomingMessage } from 'http';
import { ChatPlugin } from './plugins/chat-plugin';
// eslint-disable-next-line @typescript-eslint/no-var-requires
const PgSimplifyInflectorPlugin = require('@graphile-contrib/pg-simplify-inflector');

@Injectable()
export class PostGraphileService implements OnModuleInit {
  private readonly logger = new Logger(PostGraphileService.name);
  private readonly pool: Pool;
  private readonly middleware: ReturnType<typeof postgraphile>;

  constructor(private readonly httpAdapterHost: HttpAdapterHost) {
    const connectionString =
      process.env.DATABASE_URL ||
      'postgres://user:password@postgres:5432/agent_db';

    this.pool = new Pool({ connectionString });

    const options: PostGraphileOptions = {
      // Watch DB schema for changes in development
      watchPg: process.env.NODE_ENV !== 'production',
      // Dynamic JSON support
      dynamicJson: true,
      // GraphiQL IDE for development
      graphiql: process.env.NODE_ENV !== 'production',
      enhanceGraphiql: process.env.NODE_ENV !== 'production',
      // CORS handled by NestJS
      enableCors: false,
      // Relay Node interface (global IDs)
      classicIds: false,
      nodeIdFieldName: 'id',
      // Cursor-based pagination connections + simple collections
      simpleCollections: 'both',
      // Cleaner GraphQL names via pg-simplify-inflector + custom mutations
      appendPlugins: [PgSimplifyInflectorPlugin, ChatPlugin],
      // GraphQL route
      graphqlRoute: '/graphql',
      graphiqlRoute: '/graphiql',
      // Expose errors in development
      showErrorStack: process.env.NODE_ENV !== 'production',
      extendedErrors:
        process.env.NODE_ENV !== 'production'
          ? ['hint', 'detail', 'errcode']
          : [],
      // Omit legacy relations
      legacyRelations: 'omit' as const,
      // Retry on DB connection init
      retryOnInitFail: true,
      // Pass userId from JWT auth middleware into PostgreSQL session settings
      // This enables row-level security and user-scoped queries
      pgSettings: (req: IncomingMessage) => {
        const userId = (req as any).userId;
        return {
          'app.current_user_id': userId ? String(userId) : '',
        };
      },
    };

    this.middleware = postgraphile(this.pool, 'public', options);
    this.logger.log('PostGraphile middleware created');
    this.logger.log(`Database URL: ${connectionString.replace(/\/\/.*@/, '//*****@')}`);
  }

  async onModuleInit(): Promise<void> {
    const httpAdapter = this.httpAdapterHost.httpAdapter;
    const app = httpAdapter.getInstance();

    // Mount PostGraphile middleware on Express (handles /graphql and /graphiql)
    app.use(this.middleware);

    this.logger.log('PostGraphile middleware mounted (routes: /graphql, /graphiql)');
  }

  getPool(): Pool {
    return this.pool;
  }
}
