import OpenAI from 'openai';

const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

const MODEL = 'text-embedding-3-small';
const MAX_TOKENS = 8000; // stay under 8191 limit with buffer

export async function embedText(text: string): Promise<number[]> {
  // Truncate by character estimate (~4 chars per token) if too long
  const truncated = text.length > MAX_TOKENS * 4 ? text.slice(-MAX_TOKENS * 4) : text;

  const response = await client.embeddings.create({
    model: MODEL,
    input: truncated,
  });

  return response.data[0].embedding;
}
