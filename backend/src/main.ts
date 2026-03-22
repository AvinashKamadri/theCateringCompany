import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import * as cookieParser from 'cookie-parser';

async function bootstrap() {
  const app = await NestFactory.create(AppModule, {
    rawBody: true,
  });

  app.use(cookieParser());

  // CORS: use CORS_ORIGIN env var in production, allow all in development
  const corsOrigin = process.env.CORS_ORIGIN
    ? process.env.CORS_ORIGIN.split(',').map((o) => o.trim())
    : true;

  app.enableCors({
    origin: corsOrigin,
    credentials: true,
    methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization', 'Cookie'],
    exposedHeaders: ['Set-Cookie'],
  });

  app.setGlobalPrefix('api');

  const port = process.env.BACKEND_PORT || 3001;
  await app.listen(port);
  console.log(`🚀 Backend running on port ${port}`);
  console.log(`✅ CORS origin: ${JSON.stringify(corsOrigin)}`);
}
bootstrap();
