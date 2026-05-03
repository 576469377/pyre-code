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

  const userRes = await fetch(`${GRADING_SERVICE_URL}/users/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username }),
  });
  if (!userRes.ok) return NextResponse.json({ progress: {} });

  const { userId } = await userRes.json();
  const progressRes = await fetch(`${GRADING_SERVICE_URL}/progress/${userId}`);
  if (!progressRes.ok) return NextResponse.json({ progress: {} });

  const progress = await progressRes.json();
  return NextResponse.json({ progress });
}
