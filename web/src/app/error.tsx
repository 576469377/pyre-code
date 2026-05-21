'use client';

import { useEffect } from 'react';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('Uncaught error:', error);
  }, [error]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg p-6">
      <div className="text-center max-w-sm">
        <div
          className="w-12 h-12 mx-auto mb-4 rounded-xl flex items-center justify-center text-2xl"
          style={{ background: 'var(--bg-sunken, #f5f5f5)', border: '1px solid var(--line, #e5e5e5)' }}
        >
          ⚠️
        </div>
        <h2 className="text-lg font-semibold mb-2" style={{ color: 'var(--text, #1a1a1a)' }}>
          Something went wrong
        </h2>
        <p className="text-sm mb-4" style={{ color: 'var(--text-2, #666)' }}>
          {error.message || 'An unexpected error occurred.'}
        </p>
        <button
          onClick={reset}
          className="px-4 py-2 rounded-lg text-sm font-medium text-white cursor-pointer"
          style={{ background: 'var(--accent, #0066ff)' }}
        >
          Try again
        </button>
      </div>
    </div>
  );
}
