import prisma from './prisma';
import { decryptToken } from './token-crypto';
import logger from './logger';

const GMAIL_BASE = 'https://gmail.googleapis.com/gmail/v1/users/me';

// ── Token management ──────────────────────────────────────────────────────────

export async function getValidAccessToken(userId: string): Promise<string> {
  const account = await prisma.oauth_accounts.findFirst({
    where: { user_id: userId, provider: 'google' },
  });
  if (!account?.access_token) throw new Error(`Gmail not connected for user ${userId}`);

  const fiveMinFromNow = new Date(Date.now() + 5 * 60 * 1000);
  const needsRefresh =
    !account.access_token_expires_at ||
    account.access_token_expires_at < fiveMinFromNow;

  if (!needsRefresh) return account.access_token;
  if (!account.refresh_token_encrypted) throw new Error('No refresh token stored');

  logger.info({ userId }, 'Refreshing Gmail access token');

  const refreshToken = decryptToken(account.refresh_token_encrypted);
  const res = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      refresh_token: refreshToken,
      client_id: process.env.GMAIL_CLIENT_ID!,
      client_secret: process.env.GMAIL_CLIENT_SECRET!,
      grant_type: 'refresh_token',
    }),
  });

  const tokens: any = await res.json();
  if (tokens.error) throw new Error(`Token refresh failed: ${tokens.error_description}`);

  const newExpiry = new Date(Date.now() + tokens.expires_in * 1000);
  await prisma.oauth_accounts.update({
    where: { id: account.id },
    data: { access_token: tokens.access_token, access_token_expires_at: newExpiry },
  });

  return tokens.access_token;
}

// ── Gmail API calls ───────────────────────────────────────────────────────────

export interface GmailMessageRef {
  id: string;
  threadId: string;
}

export interface GmailHistoryResult {
  messageIds: GmailMessageRef[];
  newHistoryId: string;
}

export interface GmailMessage {
  id: string;
  threadId: string;
  internalDate: string;
  payload: GmailPayload;
}

export interface GmailPayload {
  mimeType: string;
  headers: { name: string; value: string }[];
  body?: { data?: string; size: number };
  parts?: GmailPayload[];
}

async function gmailGet(accessToken: string, path: string): Promise<any> {
  const res = await fetch(`${GMAIL_BASE}${path}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (res.status === 429) throw new Error('Gmail API rate limit — will retry');
  if (!res.ok) throw new Error(`Gmail API error ${res.status}: ${await res.text()}`);
  return res.json();
}

// Incremental: fetch message IDs added since startHistoryId
export async function fetchHistoryMessageIds(
  accessToken: string,
  startHistoryId: string,
): Promise<GmailHistoryResult> {
  const messageIds: GmailMessageRef[] = [];
  let pageToken: string | undefined;
  let latestHistoryId = startHistoryId;

  do {
    const params = new URLSearchParams({
      startHistoryId,
      historyTypes: 'messageAdded',
      ...(pageToken ? { pageToken } : {}),
    });

    const data = await gmailGet(accessToken, `/history?${params}`);
    latestHistoryId = data.historyId ?? latestHistoryId;

    for (const record of data.history ?? []) {
      for (const added of record.messagesAdded ?? []) {
        const msg = added.message;
        // Only process INBOX messages — skip sent, drafts, spam
        if (msg?.labelIds?.includes('INBOX')) {
          messageIds.push({ id: msg.id, threadId: msg.threadId });
        }
      }
    }

    pageToken = data.nextPageToken;
  } while (pageToken);

  return { messageIds, newHistoryId: latestHistoryId };
}

// Initial full sync: list all message IDs (paginated)
export async function listAllMessageIds(
  accessToken: string,
  pageToken?: string,
): Promise<{ messageIds: GmailMessageRef[]; nextPageToken?: string; historyId?: string }> {
  const params = new URLSearchParams({
    labelIds: 'INBOX',
    maxResults: '100',
    ...(pageToken ? { pageToken } : {}),
  });

  const data = await gmailGet(accessToken, `/messages?${params}`);
  const messageIds: GmailMessageRef[] = (data.messages ?? []).map((m: any) => ({
    id: m.id,
    threadId: m.threadId,
  }));

  return {
    messageIds,
    nextPageToken: data.nextPageToken,
    historyId: data.historyId,
  };
}

// Fetch a single message with full payload
export async function fetchMessage(
  accessToken: string,
  messageId: string,
): Promise<GmailMessage> {
  return gmailGet(accessToken, `/messages/${messageId}?format=full`);
}

export interface GmailThread {
  id: string;
  messages: GmailMessage[];
}

// Fetch full thread with all messages in order
export async function fetchThread(
  accessToken: string,
  threadId: string,
): Promise<GmailThread> {
  return gmailGet(accessToken, `/threads/${threadId}?format=full`);
}
