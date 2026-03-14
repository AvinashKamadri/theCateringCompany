import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import axios, { AxiosInstance } from 'axios';
import { v4 as uuidv4 } from 'uuid';

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
  private readonly signingBaseUrl: string;

  constructor(private readonly configService: ConfigService) {
    this.enabled =
      this.configService.get('DOCUSEAL_ENABLED') === 'true' ||
      this.configService.get('OPENSIGN_ENABLED') === 'true';

    const apiKey =
      this.configService.get('DOCUSEAL_API_KEY') ||
      this.configService.get('OPENSIGN_API_KEY');
    const apiUrl =
      this.configService.get('DOCUSEAL_API_URL') || 'https://api.docuseal.co';
    this.signingBaseUrl =
      this.configService.get('DOCUSEAL_SIGNING_URL') || 'https://docuseal.co';

    this.client = axios.create({
      baseURL: apiUrl,
      headers: {
        'X-Auth-Token': apiKey,
        'Content-Type': 'application/json',
      },
      timeout: 60000,
    });

    this.logger.log(
      `DocuSeal service initialized (enabled: ${this.enabled}, api: ${apiUrl})`,
    );
  }

  /**
   * Send a document for e-signature via DocuSeal
   */
  async sendDocumentForSignature(
    options: OpenSignDocumentOptions,
  ): Promise<OpenSignDocument> {
    if (!this.enabled) {
      this.logger.warn('DocuSeal is disabled, returning mock response');
      return this.mockDocumentResponse(options);
    }

    try {
      this.logger.log(`Creating DocuSeal template: ${options.name}`);

      // Step 1: Create template from PDF
      const templatePayload: any = { name: options.name };

      if (options.file_base64) {
        templatePayload.documents = [
          { name: `${options.name}.pdf`, file: options.file_base64, extract_fields: false },
        ];
      } else if (options.file_url) {
        templatePayload.documents = [
          { name: `${options.name}.pdf`, url: options.file_url, extract_fields: false },
        ];
      }

      const templateResponse = await this.client.post('/templates/pdf', templatePayload);
      const template = templateResponse.data;
      const templateId = template.id;
      this.logger.log(`Template created: ID ${templateId}`);

      // Step 2: Always replace all fields with only our Signature + Date fields.
      // We must do this even if DocuSeal detected fields from the PDF; auto-detected
      // fields often have no name/key which causes values[undefined] on submission.
      const firstSubmitterUuid = template.submitters?.[0]?.uuid;
      const firstDocUuid = template.schema?.[0]?.attachment_uuid;

      this.logger.log(`Template id=${templateId} submitters=${JSON.stringify(template.submitters)}`);
      this.logger.log(`Template schema=${JSON.stringify(template.schema)}`);
      this.logger.log(`Template auto-detected fields=${JSON.stringify(template.fields?.map((f: any) => ({ name: f.name, type: f.type, uuid: f.uuid })))}`);

      if (!firstSubmitterUuid || !firstDocUuid) {
        this.logger.error(`Cannot set signature field: submitterUuid=${firstSubmitterUuid}, docUuid=${firstDocUuid}`);
        throw new Error('DocuSeal template is missing submitter or document UUID — cannot add signature field');
      }

      // Step 2a: Clear ALL auto-detected fields first (DocuSeal PUT is additive unless cleared)
      this.logger.log('Clearing all auto-detected template fields...');
      await this.client.put(`/templates/${templateId}`, { fields: [] });
      this.logger.log('Fields cleared');

      // Step 2b: Re-fetch template to get fresh submitter/doc UUIDs after field clear
      const refreshed = await this.client.get(`/templates/${templateId}`);
      const submitterUuid = refreshed.data.submitters?.[0]?.uuid ?? firstSubmitterUuid;
      const docUuid = refreshed.data.schema?.[0]?.attachment_uuid ?? firstDocUuid;
      this.logger.log(`After clear: submitterUuid=${submitterUuid}, docUuid=${docUuid}`);

      // Find the last page index (0-based) for signature placement
      const pageCount: number = refreshed.data.schema?.[0]?.page_count ?? 1;
      const lastPage = Math.max(0, pageCount - 1);

      // Step 2c: Add only our Signature + Date fields — include explicit UUIDs so
      // DocuSeal renders name="values[{uuid}]" instead of name="values[undefined]"
      const signatureFieldUuid = uuidv4();
      const dateFieldUuid = uuidv4();
      this.logger.log(`Adding Signature (${signatureFieldUuid}) + Date (${dateFieldUuid}) fields on page ${lastPage}...`);
      await this.client.put(`/templates/${templateId}`, {
        fields: [
          {
            uuid: signatureFieldUuid,
            name: 'Signature',
            type: 'signature',
            required: true,
            submitter_uuid: submitterUuid,
            areas: [
              {
                x: 0.08,
                y: 0.88,
                w: 0.35,
                h: 0.07,
                attachment_uuid: docUuid,
                page: lastPage,
              },
            ],
          },
          {
            uuid: dateFieldUuid,
            name: 'Date',
            type: 'date',
            required: false,
            submitter_uuid: submitterUuid,
            areas: [
              {
                x: 0.55,
                y: 0.88,
                w: 0.25,
                h: 0.05,
                attachment_uuid: docUuid,
                page: lastPage,
              },
            ],
          },
        ],
      });
      this.logger.log('Template fields set: Signature + Date');

      // Step 3: Create submission (sends signing email to recipient)
      const submissionPayload: any = {
        template_id: templateId,
        send_email: true,
        submitters: options.recipients.map((r) => ({
          email: r.email,
          name: r.name,
          role: 'First Submitter',
        })),
      };

      if (options.message) {
        submissionPayload.message = {
          subject: `Please sign: ${options.name}`,
          body: options.message,
        };
      }

      this.logger.log(
        `Creating submission for: ${options.recipients.map((r) => r.email).join(', ')}`,
      );
      console.log(
        '[DEBUG] DocuSeal submission payload:',
        JSON.stringify(submissionPayload, null, 2),
      );

      const submissionResponse = await this.client.post('/submissions', submissionPayload);
      const submitters: any[] = Array.isArray(submissionResponse.data)
        ? submissionResponse.data
        : [submissionResponse.data];

      const firstSubmitter = submitters[0];
      const submissionId = String(firstSubmitter.submission_id || firstSubmitter.id);

      this.logger.log(`Submission created: ID ${submissionId}, slug: ${firstSubmitter.slug}`);
      this.logger.log(
        `Signing link: ${this.signingBaseUrl}/s/${firstSubmitter.slug}`,
      );

      return {
        id: submissionId,
        name: options.name,
        status: 'pending',
        created_at: new Date().toISOString(),
        signing_url: `${this.signingBaseUrl}/s/${firstSubmitter.slug}`,
        recipients: submitters.map((s: any) => ({
          id: String(s.id),
          email: s.email,
          name: s.name,
          status: s.status || 'awaiting',
          signing_url: `${this.signingBaseUrl}/s/${s.slug}`,
        })),
      };
    } catch (error: any) {
      this.logger.error(
        'Failed to send document via DocuSeal',
        error.response?.data || error.message,
      );
      console.log('[DEBUG] DocuSeal API error:', error.response?.data || error.message);
      console.log('[DEBUG] DocuSeal error details:', {
        status: error.response?.status,
        data: error.response?.data,
      });
      throw new Error(
        `DocuSeal API error: ${JSON.stringify(error.response?.data) || error.message}`,
      );
    }
  }

  /**
   * Get submission status from DocuSeal
   */
  async getDocumentStatus(documentId: string): Promise<OpenSignDocument> {
    if (!this.enabled) {
      return this.mockDocumentResponse({ name: 'Mock Document', recipients: [] });
    }

    try {
      const response = await this.client.get(`/submissions/${documentId}`);
      const data = response.data;

      return {
        id: String(data.id),
        name: data.template?.name || 'Contract',
        status: this.mapStatus(data.status),
        created_at: data.created_at || new Date().toISOString(),
        completed_at: data.completed_at,
        recipients: (data.submitters || []).map((s: any) => ({
          id: String(s.id),
          email: s.email,
          name: s.name,
          status: s.status || 'awaiting',
          signing_url: `${this.signingBaseUrl}/s/${s.slug}`,
        })),
      };
    } catch (error: any) {
      throw new Error(
        `DocuSeal API error: ${error.response?.data?.message || error.message}`,
      );
    }
  }

  /**
   * Cancel a submission in DocuSeal
   */
  async cancelDocument(documentId: string): Promise<void> {
    if (!this.enabled) return;

    try {
      await this.client.delete(`/submissions/${documentId}`);
      this.logger.log(`Submission cancelled: ${documentId}`);
    } catch (error: any) {
      throw new Error(
        `DocuSeal API error: ${error.response?.data?.message || error.message}`,
      );
    }
  }

  /**
   * Resend (not natively supported by DocuSeal)
   */
  async resendSignatureRequest(documentId: string, recipientId: string): Promise<void> {
    this.logger.warn(
      `Resend not supported by DocuSeal (submission: ${documentId}, submitter: ${recipientId})`,
    );
  }

  /**
   * Download signed document PDF
   */
  async downloadSignedDocument(documentId: string): Promise<Buffer> {
    if (!this.enabled) {
      return Buffer.from('Mock PDF content');
    }

    try {
      const response = await this.client.get(
        `/submissions/${documentId}/download`,
        { responseType: 'arraybuffer' },
      );
      return Buffer.from(response.data);
    } catch (error: any) {
      throw new Error(
        `DocuSeal API error: ${error.response?.data?.message || error.message}`,
      );
    }
  }

  private mapStatus(status: string): 'pending' | 'completed' | 'declined' | 'expired' {
    switch (status) {
      case 'completed': return 'completed';
      case 'declined': return 'declined';
      case 'expired': return 'expired';
      default: return 'pending';
    }
  }

  private mockDocumentResponse(options: OpenSignDocumentOptions): OpenSignDocument {
    const docId = `docuseal_mock_${Date.now()}`;
    return {
      id: docId,
      name: options.name,
      status: 'pending',
      created_at: new Date().toISOString(),
      signing_url: `https://docuseal.co/s/${docId}`,
      recipients: options.recipients.map((r, index) => ({
        id: `recipient_${index}`,
        email: r.email,
        name: r.name,
        status: 'awaiting',
        signing_url: `https://docuseal.co/s/${docId}_${index}`,
      })),
    };
  }
}
