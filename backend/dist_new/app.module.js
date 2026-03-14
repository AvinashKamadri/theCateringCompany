"use strict";
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.AppModule = void 0;
const common_1 = require("@nestjs/common");
const config_1 = require("@nestjs/config");
const core_1 = require("@nestjs/core");
const bullmq_1 = require("@nestjs/bullmq");
const prisma_module_1 = require("./prisma.module");
const jwt_auth_guard_1 = require("./common/guards/jwt-auth.guard");
const all_exceptions_filter_1 = require("./common/filters/all-exceptions.filter");
const auth_module_1 = require("./auth/auth.module");
const users_module_1 = require("./users/users.module");
const projects_module_1 = require("./projects/projects.module");
const contracts_module_1 = require("./contracts/contracts.module");
const messages_module_1 = require("./messages/messages.module");
const attachments_module_1 = require("./attachments/attachments.module");
const payments_module_1 = require("./payments/payments.module");
const webhooks_module_1 = require("./webhooks/webhooks.module");
const notifications_module_1 = require("./notifications/notifications.module");
const sockets_module_1 = require("./sockets/sockets.module");
const workers_producers_module_1 = require("./workers_producers/workers-producers.module");
const opensign_module_1 = require("./opensign/opensign.module");
let AppModule = class AppModule {
};
exports.AppModule = AppModule;
exports.AppModule = AppModule = __decorate([
    (0, common_1.Module)({
        imports: [
            config_1.ConfigModule.forRoot({ isGlobal: true }),
            prisma_module_1.PrismaModule,
            bullmq_1.BullModule.forRootAsync({
                imports: [config_1.ConfigModule],
                inject: [config_1.ConfigService],
                useFactory: (configService) => {
                    const redisUrl = configService.get('REDIS_URL', 'redis://localhost:6379');
                    const url = new URL(redisUrl);
                    return {
                        connection: {
                            host: url.hostname,
                            port: parseInt(url.port, 10) || 6379,
                        },
                    };
                },
            }),
            auth_module_1.AuthModule,
            users_module_1.UsersModule,
            projects_module_1.ProjectsModule,
            contracts_module_1.ContractsModule,
            messages_module_1.MessagesModule,
            attachments_module_1.AttachmentsModule,
            payments_module_1.PaymentsModule,
            webhooks_module_1.WebhooksModule,
            notifications_module_1.NotificationsModule,
            sockets_module_1.SocketsModule,
            workers_producers_module_1.WorkersProducersModule,
            opensign_module_1.OpenSignModule,
        ],
        providers: [
            {
                provide: core_1.APP_GUARD,
                useClass: jwt_auth_guard_1.JwtAuthGuard,
            },
            {
                provide: core_1.APP_FILTER,
                useClass: all_exceptions_filter_1.AllExceptionsFilter,
            },
        ],
    })
], AppModule);
//# sourceMappingURL=app.module.js.map