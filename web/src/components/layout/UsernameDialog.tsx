'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useUser } from '@/context/UserContext';
import { useLocale } from '@/context/LocaleContext';

interface UsernameDialogProps {
  open: boolean;
  onClose: () => void;
}

export function UsernameDialog({ open, onClose }: UsernameDialogProps) {
  const { login } = useUser();
  const { t } = useLocale();
  const router = useRouter();
  const [value, setValue] = useState('');

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = value.trim();
    if (trimmed) {
      login(trimmed);
      setValue('');
      onClose();
      router.refresh();
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="username-dialog-title"
    >
      <div
        className="bg-white rounded-xl shadow-xl p-6 w-80"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="username-dialog-title" className="text-lg font-semibold text-text-primary mb-2">
          {t('loginPrompt')}
        </h2>
        <form onSubmit={handleSubmit}>
          <input
            type="text"
            maxLength={32}
            autoFocus
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={t('usernamePlaceholder')}
            aria-label={t('usernamePlaceholder')}
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 mb-4"
          />
          <div className="flex gap-2 justify-end">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 text-sm text-text-secondary hover:text-text-primary rounded-lg hover:bg-gray-100 transition-colors"
            >
              {t('cancel')}
            </button>
            <button
              type="submit"
              disabled={!value.trim()}
              className="px-3 py-1.5 text-sm font-medium text-white bg-accent rounded-lg hover:bg-accent/90 transition-colors disabled:opacity-50"
            >
              {t('loginButton')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
