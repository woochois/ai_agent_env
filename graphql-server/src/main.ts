import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  // Enable CORS for frontend access
  app.enableCors({
    origin: true,
    credentials: true,
  });

  const port = process.env.PORT || 4000;
  await app.listen(port);

  console.log(`🚀 GraphQL server running on http://localhost:${port}`);
  console.log(`📡 PostGraphile GraphQL endpoint: http://localhost:${port}/graphql`);
}

bootstrap();
