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
Object.defineProperty(exports, "__esModule", { value: true });
exports.MessagesService = void 0;
const common_1 = require("@nestjs/common");
const prisma_service_1 = require("../prisma.service");
let MessagesService = class MessagesService {
    constructor(prisma) {
        this.prisma = prisma;
    }
    async listThreads(projectId) {
        return this.prisma.threads.findMany({
            where: { project_id: projectId },
            orderBy: { last_activity_at: 'desc' },
        });
    }
    async getThread(threadId, page, limit) {
        const thread = await this.prisma.threads.findUnique({
            where: { id: threadId },
        });
        if (!thread) {
            throw new common_1.NotFoundException(`Thread ${threadId} not found`);
        }
        const skip = (page - 1) * limit;
        const [messages, totalMessages] = await Promise.all([
            this.prisma.messages.findMany({
                where: { thread_id: threadId, is_deleted: false },
                orderBy: { created_at: 'asc' },
                skip,
                take: limit,
                include: {
                    message_mentions: {
                        select: {
                            mentioned_user_id: true,
                        },
                    },
                },
            }),
            this.prisma.messages.count({
                where: { thread_id: threadId, is_deleted: false },
            }),
        ]);
        const transformedMessages = messages.map((msg) => ({
            ...msg,
            mentioned_user_ids: msg.message_mentions.map((m) => m.mentioned_user_id),
            message_mentions: undefined,
        }));
        return {
            thread,
            messages: transformedMessages,
            pagination: {
                page,
                limit,
                totalMessages,
                totalPages: Math.ceil(totalMessages / limit),
            },
        };
    }
    async createThread(userId, projectId, dto) {
        return this.prisma.threads.create({
            data: {
                project_id: projectId,
                subject: dto.subject ?? null,
                created_by: userId,
                last_activity_at: new Date(),
            },
        });
    }
    async createMessage(userId, threadId, dto) {
        const thread = await this.prisma.threads.findUnique({
            where: { id: threadId },
        });
        if (!thread) {
            throw new common_1.NotFoundException(`Thread ${threadId} not found`);
        }
        const projectId = thread.project_id;
        const mentionedUserIds = dto.mentionedUserIds || this.extractMentions(dto.content);
        const result = await this.prisma.$transaction(async (tx) => {
            const message = await tx.messages.create({
                data: {
                    thread_id: threadId,
                    project_id: projectId,
                    author_id: userId,
                    sender_type: 'user',
                    content: dto.content,
                    parent_message_id: dto.parentMessageId ?? null,
                },
            });
            if (mentionedUserIds.length > 0) {
                await tx.message_mentions.createMany({
                    data: mentionedUserIds.map((mentionedUserId) => ({
                        message_id: message.id,
                        mentioned_user_id: mentionedUserId,
                        mention_type: 'direct',
                    })),
                });
            }
            await tx.threads.update({
                where: { id: threadId },
                data: {
                    last_activity_at: new Date(),
                    message_count: { increment: 1 },
                },
            });
            return message;
        });
        return { message: result, projectId, mentionedUserIds };
    }
    extractMentions(content) {
        const mentionRegex = /@\[([a-f0-9-]+):[^\]]+\]/g;
        const mentions = [];
        let match;
        while ((match = mentionRegex.exec(content)) !== null) {
            mentions.push(match[1]);
        }
        return mentions;
    }
    async getProjectCollaborators(projectId) {
        const collaborators = await this.prisma.project_collaborators.findMany({
            where: { project_id: projectId },
            include: {
                users: {
                    select: {
                        id: true,
                        email: true,
                        primary_phone: true,
                    },
                },
            },
        });
        return collaborators.map((c) => ({
            id: c.users.id,
            email: c.users.email,
            role: c.role,
        }));
    }
};
exports.MessagesService = MessagesService;
exports.MessagesService = MessagesService = __decorate([
    (0, common_1.Injectable)(),
    __metadata("design:paramtypes", [prisma_service_1.PrismaService])
], MessagesService);
//# sourceMappingURL=messages.service.js.map