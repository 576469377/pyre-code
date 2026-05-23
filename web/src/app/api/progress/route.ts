import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { GRADING_SERVICE_URL } from '@/lib/constants';

export async function GET() {
  const cookieStore = await cookies();
  const raw = cookieStore.get('pyre_username')?.value;
  const username = raw ? decodeURIComponent(raw) : undefined;

  if (!username) {
    return NextResponse.json({ progress: {} });
  }

  const progressRes = await fetch(`${GRADING_SERVICE_URL}/progress/by-username/${encodeURIComponent(username)}`);
  if (!progressRes.ok) return NextResponse.json({ progress: {} });

  const progress = await progressRes.json();
  return NextResponse.json({ progress });
}
