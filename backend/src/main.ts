import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import * as cookieParser from 'cookie-parser';
import { OpenSignService } from './opensign/opensign.service';

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

  // Auto-register DocuSeal webhook so signed-contract events flow back in
  const webhookBase = process.env.WEBHOOK_BASE_URL || process.env.BACKEND_PUBLIC_URL;
  if (webhookBase) {
    try {
      const openSign = app.get(OpenSignService, { strict: false });
      await openSign.ensureWebhookRegistered(webhookBase).catch(() => {});
    } catch {
      console.warn('⚠️  Could not resolve OpenSignService for webhook registration');
    }
  } else {
    console.warn('⚠️  WEBHOOK_BASE_URL not set — DocuSeal webhook not auto-registered. Set WEBHOOK_BASE_URL=https://your-backend-domain in .env');
  }
}
bootstrap();
