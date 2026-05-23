'use client';

import { useUser } from '@/context/UserContext';
import { AuthDialog } from '@/components/layout/AuthDialog';

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { username } = useUser();

  if (!username) {
    return <AuthDialog open={true} />;
  }

  return <>{children}</>;
}
