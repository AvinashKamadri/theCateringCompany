import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import axios, { AxiosInstance } from 'axios';

export interface SignWellRecipient {
  email: string;
  name: string;
  role?: 'signer' | 'cc' | 'approver';
  order?: number;
}

export interface SignWellDocumentOptions {
  name: string;
  recipients: SignWellRecipient[];
  file_url?: string;
  file_base64?: string;
  test_mode?: boolean;
  redirect_url?: string;
  message?: string;
}

export interface SignWellDocument {
  id: string;
  name: string;
  status: 'pending' | 'completed' | 'declined' | 'expired';
  created_at: string;
  completed_at?: string;
  signing_url?: string;
  recipients: Array<{
    id: string;
    email: string;
    name: string;
    status: string;
    signing_url?: string;
  }>;
}

@Injectable()
export class SignWellService {
  private readonly logger = new Logger(SignWellService.name);
  private readonly client: AxiosInstance;
  private readonly enabled: boolean;
  private readonly testMode: boolean;

  constructor(private readonly configService: ConfigService) {
    this.enabled = this.configService.get('SIGNWELL_ENABLED') === 'true';
    this.testMode = this.configService.get('SIGNWELL_TEST_MODE') === 'true';

    const apiKey = this.configService.get('SIGNWELL_API_KEY');
    const apiUrl =
      this.configService.get('SIGNWELL_API_URL') ||
      'https://www.signwell.com/api/v1';

    this.client = axios.create({
      baseURL: apiUrl,
      headers: {
        'X-Api-Key': apiKey,
        'Content-Type': 'application/json',
      },
    });

    this.logger.log(
      `SignWell service initialized (enabled: ${this.enabled}, test mode: ${this.testMode})`,
    );
  }

  /**
   * Send a document for e-signature via SignWell
   */
  async sendDocumentForSignature(
    options: SignWellDocumentOptions,
  ): Promise<SignWellDocument> {
    if (!this.enabled) {
      this.logger.warn('SignWell is disabled, returning mock response');
      return this.mockDocumentResponse(options);
    }

    try {
      this.logger.log(`Sending document to SignWell: ${options.name}`);

      const payload = {
        name: options.name,
        recipients: options.recipients.map((r, index) => ({
          email: r.email,
          name: r.name,
          role: r.role || 'signer',
          order: r.order ?? index + 1,
        })),
        test_mode: this.testMode,
        ...(options.file_url && { file_url: options.file_url }),
        ...(options.file_base64 && { file: options.file_base64 }),
        ...(options.redirect_url && { redirect_url: options.redirect_url }),
        ...(options.message && { message: options.message }),
      };

      const response = await this.client.post('/documents', payload);

      this.logger.log(
        `Document sent successfully. ID: ${response.data.id}`,
      );

      return response.data;
    } catch (error: any) {
      this.logger.error('Failed to send document to SignWell', error.response?.data || error.message);
      throw new Error(
        `SignWell API error: ${error.response?.data?.message || error.message}`,
      );
    }
  }

  /**
   * Get document status from SignWell
   */
  async getDocumentStatus(documentId: string): Promise<SignWellDocument> {
    if (!this.enabled) {
      this.logger.warn('SignWell is disabled, returning mock status');
      return this.mockDocumentResponse({ name: 'Mock Document', recipients: [] });
    }

    try {
      const response = await this.client.get(`/documents/${documentId}`);
      return response.data;
    } catch (error: any) {
      this.logger.error('Failed to get document status', error.response?.data || error.message);
      throw new Error(
        `SignWell API error: ${error.response?.data?.message || error.message}`,
      );
    }
  }

  /**
   * Cancel a document in SignWell
   */
  async cancelDocument(documentId: string): Promise<void> {
    if (!this.enabled) {
      this.logger.warn('SignWell is disabled, skipping cancel');
      return;
    }

    try {
      await this.client.delete(`/documents/${documentId}`);
      this.logger.log(`Document cancelled: ${documentId}`);
    } catch (error: any) {
      this.logger.error('Failed to cancel document', error.response?.data || error.message);
      throw new Error(
        `SignWell API error: ${error.response?.data?.message || error.message}`,
      );
    }
  }

  /**
   * Resend signature request to recipient
   */
  async resendSignatureRequest(documentId: string, recipientId: string): Promise<void> {
    if (!this.enabled) {
      this.logger.warn('SignWell is disabled, skipping resend');
      return;
    }

    try {
      await this.client.post(`/documents/${documentId}/recipients/${recipientId}/resend`);
      this.logger.log(`Signature request resent to recipient: ${recipientId}`);
    } catch (error: any) {
      this.logger.error('Failed to resend signature request', error.response?.data || error.message);
      throw new Error(
        `SignWell API error: ${error.response?.data?.message || error.message}`,
      );
    }
  }

  /**
   * Download signed document PDF
   */
  async downloadSignedDocument(documentId: string): Promise<Buffer> {
    if (!this.enabled) {
      this.logger.warn('SignWell is disabled, returning mock PDF');
      return Buffer.from('Mock PDF content');
    }

    try {
      const response = await this.client.get(`/documents/${documentId}/completed_pdf`, {
        responseType: 'arraybuffer',
      });
      return Buffer.from(response.data);
    } catch (error: any) {
      this.logger.error('Failed to download signed document', error.response?.data || error.message);
      throw new Error(
        `SignWell API error: ${error.response?.data?.message || error.message}`,
      );
    }
  }

  /**
   * Mock response for testing when SignWell is disabled
   */
  private mockDocumentResponse(options: SignWellDocumentOptions): SignWellDocument {
    return {
      id: `mock_${Date.now()}`,
      name: options.name,
      status: 'pending',
      created_at: new Date().toISOString(),
      signing_url: 'https://signwell.com/mock-signing-url',
      recipients: options.recipients.map((r, index) => ({
        id: `recipient_${index}`,
        email: r.email,
        name: r.name,
        status: 'pending',
        signing_url: `https://signwell.com/s/mock-${index}`,
      })),
    };
  }
}
