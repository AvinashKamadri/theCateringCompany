import { createDecipheriv } from 'crypto';

function encryptionKey(): Buffer {
  const key = process.env.GMAIL_TOKEN_ENCRYPTION_KEY;
  if (!key) throw new Error('GMAIL_TOKEN_ENCRYPTION_KEY not set');
  return Buffer.from(key, 'hex');
}

export function decryptToken(encrypted: string): string {
  const key = encryptionKey();
  const buf = Buffer.from(encrypted, 'base64');
  const iv = buf.subarray(0, 12);
  const tag = buf.subarray(12, 28);
  const data = buf.subarray(28);
  const decipher = createDecipheriv('aes-256-gcm', key, iv);
  decipher.setAuthTag(tag);
  return Buffer.concat([decipher.update(data), decipher.final()]).toString('utf8');
}
