import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { GRADING_SERVICE_URL } from '@/lib/constants';

export async function GET(_req: Request, { params }: { params: Promise<{ taskId: string }> }) {
  const { taskId } = await params;
  const cookieStore = await cookies();
  const raw = cookieStore.get('pyre_username')?.value;
  const username = raw ? decodeURIComponent(raw) : undefined;
  if (!username) return NextResponse.json([]);

  const res = await fetch(`${GRADING_SERVICE_URL}/submissions/by-username/${encodeURIComponent(username)}/${encodeURIComponent(taskId)}`);
  if (!res.ok) return NextResponse.json([]);
  return NextResponse.json(await res.json());
}
