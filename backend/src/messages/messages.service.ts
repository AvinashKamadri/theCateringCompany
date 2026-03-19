import { Injectable, NotFoundException, ForbiddenException, HttpException, HttpStatus } from '@nestjs/common';
import { PrismaService } from '../prisma.service';

// Roles that may NOT send messages at all
const SILENT_ROLES = ['viewer'];
// Roles that are rate-limited (messages per hour)
const RATE_LIMITED_ROLES = ['collaborator'];
const RATE_LIMIT_MAX = 20;           // max messages
const RATE_LIMIT_WINDOW_MS = 60 * 60 * 1000; // 1 hour

interface CreateThreadDto {
  subject?: string;
}

interface CreateMessageDto {
  content: string;
  parentMessageId?: string;
  mentionedUserIds?: string[];
}

@Injectable()
export class MessagesService {
  constructor(private readonly prisma: PrismaService) {}

  // ─── In-memory rate limiter ──────────────────────────────────────────────────
  // key: `${projectId}:${userId}` → { count, windowStart }
  private readonly rlStore = new Map<string, { count: number; windowStart: number }>();

  /**
   * Returns { allowed, remaining, resetAt } for the given key.
   * Automatically opens a new window if the old one expired.
   */
  private checkRateLimit(key: string): { allowed: boolean; remaining: number; resetAt: number } {
    const now = Date.now();
    const entry = this.rlStore.get(key);

    if (!entry || now - entry.windowStart >= RATE_LIMIT_WINDOW_MS) {
      this.rlStore.set(key, { count: 1, windowStart: now });
      return { allowed: true, remaining: RATE_LIMIT_MAX - 1, resetAt: now + RATE_LIMIT_WINDOW_MS };
    }

    if (entry.count >= RATE_LIMIT_MAX) {
      return { allowed: false, remaining: 0, resetAt: entry.windowStart + RATE_LIMIT_WINDOW_MS };
    }

    entry.count += 1;
    return {
      allowed: true,
      remaining: RATE_LIMIT_MAX - entry.count,
      resetAt: entry.windowStart + RATE_LIMIT_WINDOW_MS,
    };
  }

  /**
   * Enforces role-based send permission and rate limiting.
   * Returns rate-limit metadata to attach to the response.
   */
  private async enforceMessagePolicy(
    userId: string,
    projectId: string,
  ): Promise<{ role: string; remaining: number | null; resetAt: number | null }> {
    const membership = await this.prisma.project_collaborators.findUnique({
      where: { project_id_user_id: { project_id: projectId, user_id: userId } },
    });

    // Non-members still allowed (AI bot, staff, etc.) — no restriction
    if (!membership) return { role: 'none', remaining: null, resetAt: null };

    const role = membership.role ?? 'collaborator';

    if (SILENT_ROLES.includes(role)) {
      throw new ForbiddenException('Viewers cannot send messages');
    }

    if (RATE_LIMITED_ROLES.includes(role)) {
      const rlKey = `${projectId}:${userId}`;
      const rl = this.checkRateLimit(rlKey);
      if (!rl.allowed) {
        throw new HttpException(
          `Message limit reached. Resets at ${new Date(rl.resetAt).toISOString()}`,
          HttpStatus.TOO_MANY_REQUESTS,
        );
      }
      return { role, remaining: rl.remaining, resetAt: rl.resetAt };
    }

    // owner / manager — unlimited
    return { role, remaining: null, resetAt: null };
  }

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

    // Transform messages to include mentioned_user_ids array
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
   * Enforces role permissions and rate limiting for collaborators.
   * Returns the created message, project_id, and rate-limit metadata.
   */
  async createMessage(userId: string, threadId: string, dto: CreateMessageDto) {
    const thread = await this.prisma.threads.findUnique({
      where: { id: threadId },
    });

    if (!thread) {
      throw new NotFoundException(`Thread ${threadId} not found`);
    }

    const projectId = thread.project_id;

    // Enforce message send policy (role check + rate limit)
    const rateInfo = projectId
      ? await this.enforceMessagePolicy(userId, projectId)
      : { role: 'none', remaining: null, resetAt: null };

    // Extract mentions from content if not provided
    const mentionedUserIds = dto.mentionedUserIds || this.extractMentions(dto.content);

    // Use transaction to create message and mentions atomically
    const result = await this.prisma.$transaction(async (tx) => {
      // Create the message
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

      // Create mention records if any
      if (mentionedUserIds.length > 0) {
        await tx.message_mentions.createMany({
          data: mentionedUserIds.map((mentionedUserId) => ({
            message_id: message.id,
            mentioned_user_id: mentionedUserId,
            mention_type: 'direct',
          })),
        });
      }

      // Update thread metadata: bump last_activity_at and increment message_count
      await tx.threads.update({
        where: { id: threadId },
        data: {
          last_activity_at: new Date(),
          message_count: { increment: 1 },
        },
      });

      return message;
    });

    return { message: result, projectId, mentionedUserIds, rateLimit: rateInfo };
  }

  /**
   * Extract user IDs from @mentions in message content.
   * Format: @[userId:displayName]
   */
  private extractMentions(content: string): string[] {
    const mentionRegex = /@\[([a-f0-9-]+):[^\]]+\]/g;
    const mentions: string[] = [];
    let match;

    while ((match = mentionRegex.exec(content)) !== null) {
      mentions.push(match[1]);
    }

    return mentions;
  }

  /**
   * Get project collaborators for mention autocomplete.
   */
  async getProjectCollaborators(projectId: string) {
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
}
