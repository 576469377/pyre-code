import { NextResponse } from 'next/server';
import { GRADING_SERVICE_URL } from '@/lib/constants';

export async function POST(request: Request) {
  const { username, password } = await request.json();

  if (!username || !password) {
    return NextResponse.json({ error: 'Username and password are required.' }, { status: 400 });
  }

  const res = await fetch(`${GRADING_SERVICE_URL}/users/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });

  const data = await res.json();
  if (!res.ok) {
    return NextResponse.json({ error: data.detail || 'Login failed.' }, { status: res.status });
  }

  const response = NextResponse.json({ userId: data.userId, username: data.username });
  response.cookies.set('pyre_username', data.username, {
    maxAge: 365 * 24 * 60 * 60,
    path: '/',
  });
  return response;
}
