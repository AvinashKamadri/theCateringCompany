import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import axios, { AxiosInstance } from 'axios';

export interface OpenSignRecipient {
  email: string;
  name: string;
  role?: 'signer' | 'cc' | 'approver';
  order?: number;
}

export interface OpenSignDocumentOptions {
  name: string;
  recipients: OpenSignRecipient[];
  file_base64?: string;
  file_url?: string;
  message?: string;
  redirect_url?: string;
}

export interface OpenSignDocument {
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
export class OpenSignService {
  private readonly logger = new Logger(OpenSignService.name);
  private readonly client: AxiosInstance;
  private readonly enabled: boolean;
  private readonly testMode: boolean;

  constructor(private readonly configService: ConfigService) {
    this.enabled = this.configService.get('OPENSIGN_ENABLED') === 'true';
    this.testMode = this.configService.get('OPENSIGN_TEST_MODE') === 'true';

    const apiKey = this.configService.get('OPENSIGN_API_KEY');
    const apiUrl =
      this.configService.get('OPENSIGN_API_URL') ||
      'https://app.opensignlabs.com/api/v1';

    this.client = axios.create({
      baseURL: apiUrl,
      headers: {
        'x-api-token': apiKey,
        'Content-Type': 'application/json',
      },
      timeout: 30000,
    });

    this.logger.log(
      `OpenSign service initialized (enabled: ${this.enabled}, test mode: ${this.testMode})`,
    );
  }

  /**
   * Send a document for e-signature via OpenSign
   */
  async sendDocumentForSignature(
    options: OpenSignDocumentOptions,
  ): Promise<OpenSignDocument> {
    if (!this.enabled) {
      this.logger.warn('OpenSign is disabled, returning mock response');
      return this.mockDocumentResponse(options);
    }

    try {
      this.logger.log(`Sending document to OpenSign: ${options.name}`);

      const payload = {
        name: options.name,
        signers: options.recipients.map((r, index) => ({
          email: r.email,
          name: r.name,
          role: r.role || 'signer',
          order: r.order ?? index + 1,
        })),
        ...(options.file_base64 && { file: options.file_base64 }),
        ...(options.file_url && { fileUrl: options.file_url }),
        ...(options.redirect_url && { redirectUrl: options.redirect_url }),
        ...(options.message && { message: options.message }),
        ...(this.testMode && { testMode: true }),
      };

      this.logger.log('OpenSign API payload prepared');
      console.log('[DEBUG] OpenSign payload:', JSON.stringify({ ...payload, file: payload.file ? `[${payload.file.length} bytes]` : undefined }, null, 2));

      const response = await this.client.post('/createdocument', payload);

      this.logger.log(
        `Document sent successfully. ID: ${response.data.id || response.data._id}`,
      );

      // Map OpenSign response to our standard format
      return {
        id: response.data.id || response.data._id,
        name: response.data.name,
        status: response.data.status || 'pending',
        created_at: response.data.createdAt || new Date().toISOString(),
        signing_url: response.data.signingUrl || response.data.signing_url,
        recipients: (response.data.signers || []).map((signer: any) => ({
          id: signer.id || signer._id,
          email: signer.email,
          name: signer.name,
          status: signer.status || 'pending',
          signing_url: signer.signingUrl || signer.signing_url,
        })),
      };
    } catch (error: any) {
      this.logger.error('Failed to send document to OpenSign', error.response?.data || error.message);
      console.log('[DEBUG] OpenSign API error:', error.response?.data || error.message);
      console.log('[DEBUG] OpenSign error details:', {
        status: error.response?.status,
        statusText: error.response?.statusText,
        data: error.response?.data,
      });
      throw new Error(
        `OpenSign API error: ${error.response?.data?.message || error.message}`,
      );
    }
  }

  /**
   * Get document status from OpenSign
   */
  async getDocumentStatus(documentId: string): Promise<OpenSignDocument> {
    if (!this.enabled) {
      this.logger.warn('OpenSign is disabled, returning mock status');
      return this.mockDocumentResponse({ name: 'Mock Document', recipients: [] });
    }

    try {
      const response = await this.client.get(`/documents/${documentId}`);

      return {
        id: response.data.id || response.data._id,
        name: response.data.name,
        status: response.data.status || 'pending',
        created_at: response.data.createdAt || new Date().toISOString(),
        completed_at: response.data.completedAt,
        signing_url: response.data.signingUrl || response.data.signing_url,
        recipients: (response.data.signers || []).map((signer: any) => ({
          id: signer.id || signer._id,
          email: signer.email,
          name: signer.name,
          status: signer.status || 'pending',
          signing_url: signer.signingUrl || signer.signing_url,
        })),
      };
    } catch (error: any) {
      this.logger.error('Failed to get document status', error.response?.data || error.message);
      throw new Error(
        `OpenSign API error: ${error.response?.data?.message || error.message}`,
      );
    }
  }

  /**
   * Cancel a document in OpenSign
   */
  async cancelDocument(documentId: string): Promise<void> {
    if (!this.enabled) {
      this.logger.warn('OpenSign is disabled, skipping cancel');
      return;
    }

    try {
      await this.client.delete(`/documents/${documentId}`);
      this.logger.log(`Document cancelled: ${documentId}`);
    } catch (error: any) {
      this.logger.error('Failed to cancel document', error.response?.data || error.message);
      throw new Error(
        `OpenSign API error: ${error.response?.data?.message || error.message}`,
      );
    }
  }

  /**
   * Resend signature request to recipient
   */
  async resendSignatureRequest(documentId: string, recipientId: string): Promise<void> {
    if (!this.enabled) {
      this.logger.warn('OpenSign is disabled, skipping resend');
      return;
    }

    try {
      await this.client.post(`/documents/${documentId}/signers/${recipientId}/resend`);
      this.logger.log(`Signature request resent to recipient: ${recipientId}`);
    } catch (error: any) {
      this.logger.error('Failed to resend signature request', error.response?.data || error.message);
      throw new Error(
        `OpenSign API error: ${error.response?.data?.message || error.message}`,
      );
    }
  }

  /**
   * Download signed document PDF
   */
  async downloadSignedDocument(documentId: string): Promise<Buffer> {
    if (!this.enabled) {
      this.logger.warn('OpenSign is disabled, returning mock PDF');
      return Buffer.from('Mock PDF content');
    }

    try {
      const response = await this.client.get(`/documents/${documentId}/download`, {
        responseType: 'arraybuffer',
      });
      return Buffer.from(response.data);
    } catch (error: any) {
      this.logger.error('Failed to download signed document', error.response?.data || error.message);
      throw new Error(
        `OpenSign API error: ${error.response?.data?.message || error.message}`,
      );
    }
  }

  /**
   * Mock response for testing when OpenSign is disabled
   */
  private mockDocumentResponse(options: OpenSignDocumentOptions): OpenSignDocument {
    const docId = `opensign_mock_${Date.now()}`;
    return {
      id: docId,
      name: options.name,
      status: 'pending',
      created_at: new Date().toISOString(),
      signing_url: `https://app.opensignlabs.com/sign/${docId}`,
      recipients: options.recipients.map((r, index) => ({
        id: `recipient_${index}`,
        email: r.email,
        name: r.name,
        status: 'pending',
        signing_url: `https://app.opensignlabs.com/sign/${docId}/${index}`,
      })),
    };
  }
}
