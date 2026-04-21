import prisma from './prisma';
import logger from './logger';

export interface IdentityResult {
  userId: string;
  identityConfidence: 'high' | 'medium';
}

export type ProjectResolution =
  | { projectId: string; status: 'resolved' }
  | { projectId: null; status: 'none' }       // zero active → caller should auto-create
  | { projectId: null; status: 'ambiguous' };  // 2+ active, can't decide → store without project

export async function resolveProjectFromThread(gmailThreadId: string): Promise<string | null> {
  const chunk = await prisma.email_chunks.findFirst({
    where: { gmail_thread_id: gmailThreadId, project_id: { not: null } },
    select: { project_id: true },
  });
  return chunk?.project_id ?? null;
}

export async function resolveClientProject(
  userId: string,
  clientEmail?: string,
  emailContent?: string, // subject + body snippet for keyword scoring
): Promise<ProjectResolution> {
  const CLOSED_STATUSES = ['completed', 'cancelled'];

  const collabs = await prisma.project_collaborators.findMany({
    where: { user_id: userId },
    include: {
      projects: {
        select: { id: true, updated_at: true, deleted_at: true, status: true, title: true, event_date: true },
      },
    },
  });

  const active = collabs
    .filter((c) => !c.projects.deleted_at && !CLOSED_STATUSES.includes(c.projects.status))
    .sort((a, b) => b.projects.updated_at.getTime() - a.projects.updated_at.getTime());

  if (active.length === 0) {
    // Check pending invitation by email
    if (clientEmail) {
      const invite = await prisma.pending_invitations.findFirst({
        where: { invited_email: clientEmail, status: 'pending' },
        orderBy: { created_at: 'desc' },
        select: { project_id: true },
      });
      if (invite) return { projectId: invite.project_id, status: 'resolved' };
    }
    return { projectId: null, status: 'none' };
  }

  if (active.length === 1) return { projectId: active[0].project_id, status: 'resolved' };

  // 2+ active projects — try keyword scoring against title + event_date
  if (emailContent) {
    const scores = active.map((c) => ({
      projectId: c.project_id,
      score: scoreEmailAgainstProject(emailContent, c.projects),
    }));
    scores.sort((a, b) => b.score - a.score);

    const topScore = scores[0].score;
    const runnerUp = scores[1].score;

    // Confident only if top scorer has points AND is clearly ahead
    if (topScore > 0 && topScore > runnerUp) {
      logger.debug({ topScore, runnerUp, projectId: scores[0].projectId }, 'Multi-project: keyword match resolved');
      return { projectId: scores[0].projectId, status: 'resolved' };
    }
  }

  logger.warn({ userId, activeCount: active.length }, 'Multi-project: ambiguous — storing without project');
  return { projectId: null, status: 'ambiguous' };
}

function scoreEmailAgainstProject(
  emailContent: string,
  project: { title: string; event_date: Date | null },
): number {
  const content = emailContent.toLowerCase();
  let score = 0;

  const titleWords = project.title.toLowerCase().split(/\s+/).filter((w) => w.length > 3);
  for (const word of titleWords) {
    if (content.includes(word)) score += 2;
  }

  if (project.event_date) {
    const d = project.event_date;
    const month = d.toLocaleString('en-US', { month: 'long' }).toLowerCase();
    const monthShort = d.toLocaleString('en-US', { month: 'short' }).toLowerCase();
    if (content.includes(month)) score += 3;
    if (content.includes(monthShort)) score += 2;
    if (content.includes(d.getFullYear().toString())) score += 1;
  }

  return score;
}

export async function autoCreateProject(userId: string): Promise<string> {
  const project = await prisma.$transaction(async (tx) => {
    const newProject = await tx.projects.create({
      data: {
        owner_user_id: userId,
        title: 'Email Inquiry',
        created_via_ai_intake: true,
      },
    });

    await tx.project_collaborators.create({
      data: {
        project_id: newProject.id,
        user_id: userId,
        role: 'owner',
        added_by: userId,
      },
    });

    return newProject;
  });

  logger.info({ userId, projectId: project.id }, 'Auto-created project from email inquiry');
  return project.id;
}

export async function resolveClientIdentity(
  clientEmail: string,
  gmailThreadId: string,
): Promise<IdentityResult> {
  // 1. Exact email match in user_identities
  const existingIdentity = await prisma.user_identities.findUnique({
    where: { kind_value: { kind: 'email', value: clientEmail } },
  });

  if (existingIdentity) {
    logger.debug({ clientEmail }, 'Identity resolved via exact email match');
    return { userId: existingIdentity.user_id, identityConfidence: 'high' };
  }

  // 2. Thread inheritance — check existing chunks in the same Gmail thread
  const existingChunk = await prisma.email_chunks.findFirst({
    where: { gmail_thread_id: gmailThreadId, user_id: { not: null } },
    select: { user_id: true },
  });

  if (existingChunk?.user_id) {
    logger.debug({ clientEmail, gmailThreadId }, 'Identity inherited from thread');
    // Register email for future lookups
    await prisma.user_identities.create({
      data: {
        user_id: existingChunk.user_id,
        kind: 'email',
        value: clientEmail,
        source: 'email_auto_created',
        identity_confidence: 'medium',
      },
    }).catch(() => { /* ignore duplicate */ });

    return { userId: existingChunk.user_id, identityConfidence: 'medium' };
  }

  // 3. Check if user exists in users table (e.g. seeded/registered) but lacks an identity record
  const existingUser = await prisma.users.findUnique({ where: { email: clientEmail } });
  if (existingUser) {
    await prisma.user_identities.create({
      data: {
        user_id: existingUser.id,
        kind: 'email',
        value: clientEmail,
        source: 'email_auto_created',
        identity_confidence: 'high',
      },
    }).catch(() => { /* ignore race-condition duplicate */ });

    logger.info({ clientEmail, userId: existingUser.id }, 'Existing user linked via email identity');
    return { userId: existingUser.id, identityConfidence: 'high' };
  }

  // 4. Create new user + identity
  const newUser = await prisma.$transaction(async (tx) => {
    const user = await tx.users.create({
      data: {
        email: clientEmail,
        status: 'active',
      },
    });

    await tx.user_identities.create({
      data: {
        user_id: user.id,
        kind: 'email',
        value: clientEmail,
        source: 'email_auto_created',
        identity_confidence: 'high',
      },
    });

    return user;
  });

  logger.info({ clientEmail, userId: newUser.id }, 'New user auto-created from email');
  return { userId: newUser.id, identityConfidence: 'high' };
}
