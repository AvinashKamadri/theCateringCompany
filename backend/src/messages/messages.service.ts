import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../prisma.service';

interface CreateThreadDto {
  subject?: string;
}

interface CreateMessageDto {
  content: string;
  parentMessageId?: string;
}

@Injectable()
export class MessagesService {
  constructor(private readonly prisma: PrismaService) {}

  /**
   * List all threads for a project, ordered by last_activity_at DESC.
   */
  async listThreads(projectId: string) {
    return this.prisma.threads.findMany({
      where: { project_id: projectId },
      orderBy: { last_activity_at: 'desc' },
    });
  }

  /**
   * Get a single thread with paginated messages (ordered by created_at ASC).
   */
  async getThread(threadId: string, page: number, limit: number) {
    const thread = await this.prisma.threads.findUnique({
      where: { id: threadId },
    });

    if (!thread) {
      throw new NotFoundException(`Thread ${threadId} not found`);
    }

    const skip = (page - 1) * limit;

    const [messages, totalMessages] = await Promise.all([
      this.prisma.messages.findMany({
        where: { thread_id: threadId, is_deleted: false },
        orderBy: { created_at: 'asc' },
        skip,
        take: limit,
      }),
      this.prisma.messages.count({
        where: { thread_id: threadId, is_deleted: false },
      }),
    ]);

    return {
      thread,
      messages,
      pagination: {
        page,
        limit,
        totalMessages,
        totalPages: Math.ceil(totalMessages / limit),
      },
    };
  }

  /**
   * Create a new thread within a project.
   */
  async createThread(userId: string, projectId: string, dto: CreateThreadDto) {
    return this.prisma.threads.create({
      data: {
        project_id: projectId,
        subject: dto.subject ?? null,
        created_by: userId,
        last_activity_at: new Date(),
      },
    });
  }

  /**
   * Create a new message in a thread.
   * Returns the created message along with the project_id from the parent thread.
   */
  async createMessage(userId: string, threadId: string, dto: CreateMessageDto) {
    const thread = await this.prisma.threads.findUnique({
      where: { id: threadId },
    });

    if (!thread) {
      throw new NotFoundException(`Thread ${threadId} not found`);
    }

    const projectId = thread.project_id;

    const message = await this.prisma.messages.create({
      data: {
        thread_id: threadId,
        project_id: projectId,
        author_id: userId,
        sender_type: 'user',
        content: dto.content,
        parent_message_id: dto.parentMessageId ?? null,
      },
    });

    // Update thread metadata: bump last_activity_at and increment message_count
    await this.prisma.threads.update({
      where: { id: threadId },
      data: {
        last_activity_at: new Date(),
        message_count: { increment: 1 },
      },
    });

    return { message, projectId };
  }
}
