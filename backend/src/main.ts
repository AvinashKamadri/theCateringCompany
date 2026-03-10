import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import * as cookieParser from 'cookie-parser';

async function bootstrap() {
  const app = await NestFactory.create(AppModule, {
    rawBody: true,
  });

  app.use(cookieParser());

  // CORS Configuration - Allow all origins in development
  app.enableCors({
    origin: true, // Allow all origins in development
    credentials: true,
    methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization', 'Cookie'],
    exposedHeaders: ['Set-Cookie'],
  });

  app.setGlobalPrefix('api');

  const port = process.env.BACKEND_PORT || 3001;
  await app.listen(port);
  console.log(`🚀 Backend running on port ${port}`);
  console.log(`✅ CORS enabled for all origins`);
}
bootstrap();
