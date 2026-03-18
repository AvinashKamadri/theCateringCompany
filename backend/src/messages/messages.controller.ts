import {
  Controller,
  Get,
  Post,
  Body,
  Param,
  Query,
  UseGuards,
  Logger,
} from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { InjectQueue } from '@nestjs/bullmq';
import { Queue } from 'bullmq';
import { MessagesService } from './messages.service';
import { SocketsGateway } from '../sockets/sockets.gateway';
import { CurrentUser } from '../common/decorators/current-user.decorator';

@UseGuards(AuthGuard('jwt'))
@Controller()
export class MessagesController {
  private readonly logger = new Logger(MessagesController.name);

  constructor(
    private readonly messagesService: MessagesService,
    private readonly socketsGateway: SocketsGateway,
    @InjectQueue('vector_indexing') private readonly vectorQueue: Queue,
  ) {}

  /**
   * GET /projects/:projectId/threads
   * List threads for a project, ordered by last_activity_at DESC.
   */
  @Get('projects/:projectId/threads')
  async listThreads(@Param('projectId') projectId: string) {
    const threads = await this.messagesService.listThreads(projectId);
    return { threads };
  }

  /**
   * GET /threads/:threadId
   * Return a thread with paginated messages (ordered by created_at ASC).
   */
  @Get('threads/:threadId')
  async getThread(
    @Param('threadId') threadId: string,
    @Query('page') page?: string,
    @Query('limit') limit?: string,
  ) {
    const pageNum = page ? parseInt(page, 10) : 1;
    const limitNum = limit ? parseInt(limit, 10) : 50;
    return this.messagesService.getThread(threadId, pageNum, limitNum);
  }

  /**
   * POST /projects/:projectId/threads
   * Create a thread with optional { subject }.
   */
  @Post('projects/:projectId/threads')
  async createThread(
    @Param('projectId') projectId: string,
    @CurrentUser() user: { userId: string },
    @Body() body: { subject?: string },
  ) {
    const thread = await this.messagesService.createThread(
      user.userId,
      projectId,
      { subject: body.subject },
    );
    return { thread };
  }

  /**
   * GET /projects/:projectId/collaborators
   * Get collaborators for mention autocomplete.
   */
  @Get('projects/:projectId/collaborators')
  async getProjectCollaborators(@Param('projectId') projectId: string) {
    const collaborators = await this.messagesService.getProjectCollaborators(projectId);
    return { collaborators };
  }

  /**
   * POST /threads/:threadId/messages
   * Create a message in a thread. Emits socket event and optionally enqueues vector indexing.
   */
  @Post('threads/:threadId/messages')
  async createMessage(
    @Param('threadId') threadId: string,
    @CurrentUser() user: { userId: string },
    @Body() body: { content: string; parentMessageId?: string; mentionedUserIds?: string[] },
  ) {
    const { message, projectId, mentionedUserIds, rateLimit } = await this.messagesService.createMessage(
      user.userId,
      threadId,
      {
        content: body.content,
        parentMessageId: body.parentMessageId,
        mentionedUserIds: body.mentionedUserIds,
      },
    );

    // Emit socket event to thread and project rooms
    this.socketsGateway.emitToRoom(`thread:${threadId}`, 'message.created', message);
    this.socketsGateway.emitToRoom(`project:${projectId}`, 'message.created', message);

    // Send mention notifications to mentioned users
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

    // Enqueue vector indexing if enabled
    if (process.env.VECTOR_ENABLED === 'true') {
      try {
        await this.vectorQueue.add('vector_indexing', {
          messageId: message.id,
          threadId,
          projectId,
          content: message.content,
        });
      } catch (error) {
        this.logger.warn(
          `Failed to enqueue vector indexing for message ${message.id}: ${error}`,
        );
      }
    }

    return {
      message,
      // Include remaining quota so the frontend can show a counter for collaborators
      rate_limit: rateLimit.remaining !== null
        ? { remaining: rateLimit.remaining, reset_at: rateLimit.resetAt }
        : null,
    };
  }
}
