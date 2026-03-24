import { Injectable, Logger } from '@nestjs/common';
import { PrismaService } from '../prisma.service';
import { JobQueueService } from '../job_queue/job-queue.service';
import { S3Client, PutObjectCommand } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';
import { randomUUID } from 'crypto';
import { owner_type } from '@prisma/client';

interface CreateSignedUploadDto {
  filename: string;
  mimeType: string;
  sizeBytes: number;
  ownerType: string;
  ownerId: string;
  projectId?: string;
}

@Injectable()
export class AttachmentsService {
  private readonly logger = new Logger(AttachmentsService.name);
  private readonly s3Client: S3Client | null;
  private readonly bucketName: string;

  constructor(
    private readonly prisma: PrismaService,
    private readonly jobQueue: JobQueueService,
  ) {
    const endpoint = process.env.R2_ENDPOINT;
    const accessKeyId = process.env.R2_ACCESS_KEY;
    const secretAccessKey = process.env.R2_SECRET_KEY;

    if (endpoint && accessKeyId && secretAccessKey) {
      this.s3Client = new S3Client({
        region: 'auto',
        endpoint,
        credentials: {
          accessKeyId,
          secretAccessKey,
        },
      });
    } else {
      this.s3Client = null;
      this.logger.warn(
        'R2 environment variables (R2_ENDPOINT, R2_ACCESS_KEY, R2_SECRET_KEY) are not set. ' +
        'Presigned URL generation will return a placeholder URL.',
      );
    }

    this.bucketName = process.env.R2_BUCKET_NAME || 'catering-attachments';
  }

  /**
   * Create an attachment record and generate a presigned PUT URL for direct upload.
   */
  async createSignedUpload(userId: string, dto: CreateSignedUploadDto) {
    const storagePath = `attachments/${dto.ownerType}/${dto.ownerId}/${randomUUID()}/${dto.filename}`;

    const attachment = await this.prisma.attachments.create({
      data: {
        owner_type: dto.ownerType as owner_type,
        owner_id: dto.ownerId,
        project_id: dto.projectId ?? null,
        filename: dto.filename,
        mime_type: dto.mimeType,
        size_bytes: dto.sizeBytes,
        storage_provider: 'r2',
        storage_path: storagePath,
        virus_scan_status: 'pending',
        uploaded_by: userId,
      },
    });

    let uploadUrl: string;

    if (this.s3Client) {
      const command = new PutObjectCommand({
        Bucket: this.bucketName,
        Key: storagePath,
        ContentType: dto.mimeType,
        ContentLength: dto.sizeBytes,
      });

      uploadUrl = await getSignedUrl(this.s3Client, command, {
        expiresIn: 3600, // 1 hour
      });
    } else {
      // TODO: Replace with actual R2 presigned URL once R2_ENDPOINT, R2_ACCESS_KEY, R2_SECRET_KEY are configured
      uploadUrl = `https://placeholder.r2.dev/${this.bucketName}/${storagePath}?X-Amz-Signature=PLACEHOLDER`;
    }

    return { uploadUrl, attachmentId: attachment.id };
  }

  /**
   * Mark an attachment as uploaded and enqueue a virus scan job.
   */
  async completeUpload(attachmentId: string) {
    const attachment = await this.prisma.attachments.update({
      where: { id: attachmentId },
      data: {
        virus_scan_status: 'scanning',
      },
    });

    await this.jobQueue.send('virus_scan', {
      attachmentId: attachment.id,
      storagePath: attachment.storage_path,
    });

    return attachment;
  }
}
