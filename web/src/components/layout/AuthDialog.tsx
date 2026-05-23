'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useUser } from '@/context/UserContext';
import { useLocale } from '@/context/LocaleContext';

interface AuthDialogProps {
  open: boolean;
  onClose?: () => void;
}

export function AuthDialog({ open, onClose }: AuthDialogProps) {
  const { login } = useUser();
  const { t } = useLocale();
  const router = useRouter();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && onClose) onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    const trimmed = username.trim();
    if (!trimmed || !password) return;

    setLoading(true);
    try {
      const endpoint = mode === 'register' ? '/api/auth/register' : '/api/auth/login';
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: trimmed, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || (mode === 'register' ? t('registerFailed') : t('loginFailed')));
        return;
      }
      login(data.username);
      setUsername('');
      setPassword('');
      if (onClose) onClose();
      router.refresh();
    } catch {
      setError(t('networkError'));
    } finally {
      setLoading(false);
    }
  };

  const inputStyle = {
    background: 'var(--bg-elev)',
    border: '1px solid var(--line)',
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'color-mix(in oklab, var(--bg) 60%, transparent)', backdropFilter: 'blur(8px)' }}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="rounded-2xl p-6 w-[340px]"
        style={{ background: 'var(--bg-elev)', border: '1px solid var(--line)', boxShadow: '0 24px 48px -12px rgba(0,0,0,0.15)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-1 mb-5">
          <button
            onClick={() => { setMode('login'); setError(''); }}
            className="flex-1 py-2 text-sm font-medium rounded-lg cursor-pointer transition-[background,color] duration-150"
            style={mode === 'login' ? { background: 'var(--accent-wash)', color: 'var(--accent)' } : { color: 'var(--text-2)' }}
          >
            {t('login')}
          </button>
          <button
            onClick={() => { setMode('register'); setError(''); }}
            className="flex-1 py-2 text-sm font-medium rounded-lg cursor-pointer transition-[background,color] duration-150"
            style={mode === 'register' ? { background: 'var(--accent-wash)', color: 'var(--accent)' } : { color: 'var(--text-2)' }}
          >
            {t('register')}
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-2)' }}>
              {t('usernameLabel')}
            </label>
            <input
              type="text"
              maxLength={32}
              autoFocus
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder={t('usernamePlaceholder')}
              className="w-full px-3 py-2 rounded-lg text-sm outline-none"
              style={inputStyle}
            />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-2)' }}>
              {t('passwordLabel')}
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={t('passwordPlaceholder')}
              className="w-full px-3 py-2 rounded-lg text-sm outline-none"
              style={inputStyle}
            />
          </div>

          {error && (
            <p className="text-xs rounded-lg px-3 py-2" style={{ color: 'var(--hard)', background: 'color-mix(in oklab, var(--hard) 8%, var(--bg-elev))' }}>
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={!username.trim() || !password || loading}
            className="w-full py-2.5 rounded-lg text-sm font-medium text-white cursor-pointer disabled:opacity-50 transition-opacity"
            style={{ background: 'var(--accent)' }}
          >
            {loading ? '...' : mode === 'register' ? t('register') : t('login')}
          </button>
        </form>

        <p className="text-center text-xs mt-4" style={{ color: 'var(--text-3)' }}>
          {mode === 'login' ? t('noAccountPrompt') : t('hasAccountPrompt')}
          {' '}
          <button
            onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); }}
            className="cursor-pointer underline"
            style={{ color: 'var(--accent)' }}
          >
            {mode === 'login' ? t('register') : t('login')}
          </button>
        </p>
      </div>
    </div>
  );
}
