export interface BaseJobData {
  jobId: string;
  userId?: string;
  projectId?: string;
}

export interface WebhookJobData extends BaseJobData {
  webhookEventId: string;
}

export interface PaymentJobData extends BaseJobData {
  paymentId: string;
  paymentIntentId?: string;
}

export interface PdfJobData extends BaseJobData {
  contractId: string;
}

export interface VectorJobData extends BaseJobData {
  messageId: string;
  content: string;
}

export interface NotificationJobData extends BaseJobData {
  notificationId: string;
  channel: string;
}

export interface VirusScanJobData extends BaseJobData {
  attachmentId: string;
  storagePath: string;
}

export interface PricingJobData extends BaseJobData {
  projectPricingId: string;
  changeOrderId?: string;
}

export interface GmailSyncJobData extends BaseJobData {
  historyId?: string;
  webhookEventId?: string;
}

export interface GmailFullSyncJobData extends BaseJobData {
}
