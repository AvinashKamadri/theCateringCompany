import { QdrantClient } from '@qdrant/js-client-rest';

const COLLECTION = 'email_conversations';
const VECTOR_SIZE = 1536;

export const qdrant = new QdrantClient({
  url: process.env.QDRANT_URL ?? 'http://localhost:6333',
  apiKey: process.env.QDRANT_API_KEY || undefined,
});

export async function ensureCollection(): Promise<void> {
  const { collections } = await qdrant.getCollections();
  if (collections.some((c) => c.name === COLLECTION)) return;

  await qdrant.createCollection(COLLECTION, {
    vectors: { size: VECTOR_SIZE, distance: 'Cosine' },
  });

  // Payload indexes for filtered search
  await qdrant.createPayloadIndex(COLLECTION, { field_name: 'user_id',    field_schema: 'keyword' });
  await qdrant.createPayloadIndex(COLLECTION, { field_name: 'project_id', field_schema: 'keyword' });
}

export async function upsertConversation(
  pointId: string,
  vector: number[],
  payload: {
    user_id: string;
    project_id: string;
    client_email: string;
    full_text: string;
    message_count: number;
    last_email_at: string;
    event_title: string;
    event_date: string | null;
  },
): Promise<void> {
  await qdrant.upsert(COLLECTION, {
    wait: true,
    points: [{ id: pointId, vector, payload }],
  });
}
