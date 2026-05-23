import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import pathsData from '@/lib/paths.json';
import { GRADING_SERVICE_URL } from '@/lib/constants';
import type { LearningPath } from '@/lib/types';

export async function GET() {
  const cookieStore = await cookies();
  const raw = cookieStore.get('pyre_username')?.value;
  const username = raw ? decodeURIComponent(raw) : undefined;

  let progressMap: Record<string, { status: string }> = {};
  if (username) {
    try {
      const progressRes = await fetch(`${GRADING_SERVICE_URL}/progress/by-username/${encodeURIComponent(username)}`);
      if (progressRes.ok) progressMap = await progressRes.json();
    } catch {
      // continue without progress
    }
  }

  const paths = (pathsData.paths as LearningPath[]).map((path) => {
    const solved = path.problems.filter((id) => progressMap[id]?.status === 'solved').length;
    return { ...path, solved, total: path.problems.length };
  });

  return NextResponse.json({ paths });
}
