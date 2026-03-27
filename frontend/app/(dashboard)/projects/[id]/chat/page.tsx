"use client";

import { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';

export default function ProjectChatPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params?.id as string;

  useEffect(() => {
    router.replace(`/projects/${projectId}`);
  }, [projectId, router]);

  return null;
}
