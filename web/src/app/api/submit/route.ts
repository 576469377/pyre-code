import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { GRADING_SERVICE_URL } from '@/lib/constants';
import { SubmissionResult } from '@/lib/types';

export async function POST(request: Request) {
  const { taskId, code } = await request.json();

  const cookieStore = await cookies();
  const raw = cookieStore.get('pyre_username')?.value;
  const username = raw ? decodeURIComponent(raw) : undefined;

  // Call grading service
  const gradingResponse = await fetch(`${GRADING_SERVICE_URL}/grade`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ taskId, code }),
  });

  if (!gradingResponse.ok) {
    const errText = await gradingResponse.text();
    return NextResponse.json(
      { passed: 0, total: 0, allPassed: false, results: [], totalTimeMs: 0, error: errText },
      { status: 502 }
    );
  }

  const result: SubmissionResult = await gradingResponse.json();

  // Save progress only if user is logged in
  if (username) {
    const status = result.allPassed ? 'solved' : 'attempted';
    await fetch(`${GRADING_SERVICE_URL}/progress`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, taskId, status, execTimeMs: result.totalTimeMs }),
    });
  }

  return NextResponse.json(result);
}
