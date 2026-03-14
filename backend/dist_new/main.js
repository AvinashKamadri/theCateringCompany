"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const core_1 = require("@nestjs/core");
const app_module_1 = require("./app.module");
const cookieParser = require("cookie-parser");
async function bootstrap() {
    const app = await core_1.NestFactory.create(app_module_1.AppModule, {
        rawBody: true,
    });
    app.use(cookieParser());
    app.enableCors({
        origin: true,
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
//# sourceMappingURL=main.js.map