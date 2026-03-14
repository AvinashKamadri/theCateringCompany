"use strict";
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};
var __param = (this && this.__param) || function (paramIndex, decorator) {
    return function (target, key) { decorator(target, key, paramIndex); }
};
var MessagesController_1;
Object.defineProperty(exports, "__esModule", { value: true });
exports.MessagesController = void 0;
const common_1 = require("@nestjs/common");
const passport_1 = require("@nestjs/passport");
const bullmq_1 = require("@nestjs/bullmq");
const bullmq_2 = require("bullmq");
const messages_service_1 = require("./messages.service");
const sockets_gateway_1 = require("../sockets/sockets.gateway");
const current_user_decorator_1 = require("../common/decorators/current-user.decorator");
let MessagesController = MessagesController_1 = class MessagesController {
    constructor(messagesService, socketsGateway, vectorQueue) {
        this.messagesService = messagesService;
        this.socketsGateway = socketsGateway;
        this.vectorQueue = vectorQueue;
        this.logger = new common_1.Logger(MessagesController_1.name);
    }
    async listThreads(projectId) {
        const threads = await this.messagesService.listThreads(projectId);
        return { threads };
    }
    async getThread(threadId, page, limit) {
        const pageNum = page ? parseInt(page, 10) : 1;
        const limitNum = limit ? parseInt(limit, 10) : 50;
        return this.messagesService.getThread(threadId, pageNum, limitNum);
    }
    async createThread(projectId, user, body) {
        const thread = await this.messagesService.createThread(user.userId, projectId, { subject: body.subject });
        return { thread };
    }
    async getProjectCollaborators(projectId) {
        const collaborators = await this.messagesService.getProjectCollaborators(projectId);
        return { collaborators };
    }
    async createMessage(threadId, user, body) {
        const { message, projectId, mentionedUserIds } = await this.messagesService.createMessage(user.userId, threadId, {
            content: body.content,
            parentMessageId: body.parentMessageId,
            mentionedUserIds: body.mentionedUserIds,
        });
        this.socketsGateway.emitToRoom(`thread:${threadId}`, 'message.created', message);
        this.socketsGateway.emitToRoom(`project:${projectId}`, 'message.created', message);
        if (mentionedUserIds && mentionedUserIds.length > 0) {
            for (const mentionedUserId of mentionedUserIds) {
                this.socketsGateway.emitToUser(mentionedUserId, 'message.mentioned', {
                    messageId: message.id,
                    threadId,
                    projectId,
                    authorId: user.userId,
                });
            }
        }
        if (process.env.VECTOR_ENABLED === 'true') {
            try {
                await this.vectorQueue.add('vector_indexing', {
                    messageId: message.id,
                    threadId,
                    projectId,
                    content: message.content,
                });
            }
            catch (error) {
                this.logger.warn(`Failed to enqueue vector indexing for message ${message.id}: ${error}`);
            }
        }
        return { message };
    }
};
exports.MessagesController = MessagesController;
__decorate([
    (0, common_1.Get)('projects/:projectId/threads'),
    __param(0, (0, common_1.Param)('projectId')),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String]),
    __metadata("design:returntype", Promise)
], MessagesController.prototype, "listThreads", null);
__decorate([
    (0, common_1.Get)('threads/:threadId'),
    __param(0, (0, common_1.Param)('threadId')),
    __param(1, (0, common_1.Query)('page')),
    __param(2, (0, common_1.Query)('limit')),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String, String, String]),
    __metadata("design:returntype", Promise)
], MessagesController.prototype, "getThread", null);
__decorate([
    (0, common_1.Post)('projects/:projectId/threads'),
    __param(0, (0, common_1.Param)('projectId')),
    __param(1, (0, current_user_decorator_1.CurrentUser)()),
    __param(2, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String, Object, Object]),
    __metadata("design:returntype", Promise)
], MessagesController.prototype, "createThread", null);
__decorate([
    (0, common_1.Get)('projects/:projectId/collaborators'),
    __param(0, (0, common_1.Param)('projectId')),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String]),
    __metadata("design:returntype", Promise)
], MessagesController.prototype, "getProjectCollaborators", null);
__decorate([
    (0, common_1.Post)('threads/:threadId/messages'),
    __param(0, (0, common_1.Param)('threadId')),
    __param(1, (0, current_user_decorator_1.CurrentUser)()),
    __param(2, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String, Object, Object]),
    __metadata("design:returntype", Promise)
], MessagesController.prototype, "createMessage", null);
exports.MessagesController = MessagesController = MessagesController_1 = __decorate([
    (0, common_1.UseGuards)((0, passport_1.AuthGuard)('jwt')),
    (0, common_1.Controller)(),
    __param(2, (0, bullmq_1.InjectQueue)('vector_indexing')),
    __metadata("design:paramtypes", [messages_service_1.MessagesService,
        sockets_gateway_1.SocketsGateway,
        bullmq_2.Queue])
], MessagesController);
//# sourceMappingURL=messages.controller.js.map