import type { GmailMessage, GmailPayload } from './gmail-client';

export interface ParsedEmail {
  messageId: string;
  threadId: string;
  from: string;
  to: string;
  subject: string;
  date: string;
  rawText: string;       // text after MIME decode, before quote stripping
  cleanedText: string;   // final text ready for Step 3+
}

// ── MIME walking ──────────────────────────────────────────────────────────────

function decodeBase64Url(data: string): string {
  // Gmail uses base64url encoding (- and _ instead of + and /)
  const base64 = data.replace(/-/g, '+').replace(/_/g, '/');
  return Buffer.from(base64, 'base64').toString('utf8');
}

function extractBodyFromPayload(payload: GmailPayload): string {
  // Prefer text/plain over text/html
  if (payload.mimeType === 'text/plain' && payload.body?.data) {
    return decodeBase64Url(payload.body.data);
  }

  if (payload.mimeType === 'text/html' && payload.body?.data) {
    return htmlToText(decodeBase64Url(payload.body.data));
  }

  // Walk parts recursively — prefer text/plain branch
  if (payload.parts?.length) {
    const plainPart = payload.parts.find((p) => p.mimeType === 'text/plain');
    if (plainPart) return extractBodyFromPayload(plainPart);

    const htmlPart = payload.parts.find((p) => p.mimeType === 'text/html');
    if (htmlPart) return extractBodyFromPayload(htmlPart);

    // Recurse into nested multipart (e.g. multipart/mixed inside multipart/alternative)
    for (const part of payload.parts) {
      if (part.mimeType.startsWith('multipart/')) {
        const text = extractBodyFromPayload(part);
        if (text) return text;
      }
    }
  }

  return '';
}

// ── HTML → plaintext ──────────────────────────────────────────────────────────

export function htmlToText(html: string): string {
  return html
    .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
    .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/p>/gi, '\n\n')
    .replace(/<\/div>/gi, '\n')
    .replace(/<\/li>/gi, '\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

// ── Quoted reply stripping ────────────────────────────────────────────────────

export function stripQuotedReplies(text: string): string {
  const lines = text.split('\n');
  const cleanLines: string[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // "On Mon, Apr 20... wrote:" — Gmail-style quote header (may span 2 lines)
    if (/^On .{10,} wrote:/.test(line)) break;
    if (/^On .{5,}$/.test(line) && i + 1 < lines.length && /wrote:/.test(lines[i + 1])) break;

    // Outlook-style separator
    if (/^-{3,}\s*Original Message\s*-{3,}/i.test(line)) break;
    if (/^_{3,}/.test(line)) break;

    // Lines beginning with > (standard quote marker)
    if (/^>/.test(line)) continue;

    // Forwarded email headers
    if (/^From:\s/.test(line) && i > 2) break;

    cleanLines.push(line);
  }

  return cleanLines.join('\n').replace(/\n{3,}/g, '\n\n').trim();
}

// ── Header extraction ─────────────────────────────────────────────────────────

function getHeader(payload: GmailPayload, name: string): string {
  return (
    payload.headers.find((h) => h.name.toLowerCase() === name.toLowerCase())?.value ?? ''
  );
}

// ── Main parser ───────────────────────────────────────────────────────────────

export function parseMessage(message: GmailMessage): ParsedEmail {
  const { payload } = message;

  const from = getHeader(payload, 'From');
  const to = getHeader(payload, 'To');
  const subject = getHeader(payload, 'Subject');
  const date = getHeader(payload, 'Date');

  const rawText = extractBodyFromPayload(payload);
  const cleanedText = stripQuotedReplies(rawText);

  return {
    messageId: message.id,
    threadId: message.threadId,
    from,
    to,
    subject,
    date,
    rawText,
    cleanedText,
  };
}

// Extract bare email address from "Name <email>" format
export function extractEmail(headerValue: string): string {
  const match = headerValue.match(/<([^>]+)>/);
  return match ? match[1].toLowerCase() : headerValue.toLowerCase().trim();
}

// ── Automated / bot email detection ──────────────────────────────────────────

const NO_REPLY_PATTERNS = [
  /^no[-._]?reply@/i,
  /^noreply@/i,
  /^donotreply@/i,
  /^do[-._]not[-._]reply@/i,
  /^notifications?@/i,
  /^mailer[-._]?daemon@/i,
  /^postmaster@/i,
  /^bounce[s]?@/i,
  /^automated[-._]?mail@/i,
];

const AUTOMATED_HEADER_NAMES = [
  'auto-submitted',
  'list-unsubscribe',
  'x-auto-response-suppress',
  'x-autoreply',
  'x-autorespond',
];

// Precedence header values that indicate bulk/automated mail
const AUTOMATED_PRECEDENCE = new Set(['bulk', 'list', 'junk']);

export function isAutomatedEmail(message: GmailMessage): boolean {
  const headers = message.payload.headers;
  const get = (name: string) =>
    headers.find((h) => h.name.toLowerCase() === name.toLowerCase())?.value ?? '';

  // 1. No-reply address pattern
  const fromEmail = extractEmail(get('From'));
  if (NO_REPLY_PATTERNS.some((re) => re.test(fromEmail))) return true;

  // 2. Automation headers present (any value is enough to flag)
  for (const header of AUTOMATED_HEADER_NAMES) {
    const val = get(header);
    if (val && val.toLowerCase() !== 'no') return true;
  }

  // 3. Precedence: bulk / list / junk
  const precedence = get('Precedence').toLowerCase().trim();
  if (AUTOMATED_PRECEDENCE.has(precedence)) return true;

  return false;
}
