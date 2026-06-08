'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { Sun, Moon, User, LogOut } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useLocale } from '@/context/LocaleContext';
import { useTheme } from '@/context/ThemeContext';
import { useUser } from '@/context/UserContext';
import { AuthDialog } from '@/components/layout/AuthDialog';

interface TopNavProps {
  solvedCount?: number;
  totalCount?: number;
}

function FlameGlyph() {
  return (
    <span
      className="w-[22px] h-[22px] inline-flex items-center justify-center rounded-[6px] text-accent"
      style={{
        border: '1px solid var(--accent-line)',
        background: 'var(--accent-wash)',
      }}
    >
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
        <path
          d="M6 1.25c.6 1.8.15 2.7-.75 3.6C4 6.2 3.25 7.2 3.25 8.5a2.75 2.75 0 1 0 5.5 0c0-1-.3-1.8-1-2.6.3 1.1-.15 1.8-.8 1.8-.5 0-.85-.4-.85-1C6.1 5.6 6.7 3.9 6 1.25Z"
          fill="currentColor"
        />
      </svg>
    </span>
  );
}

export function TopNav({ solvedCount, totalCount }: TopNavProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { locale, setLocale, t } = useLocale();
  const { theme, toggleTheme } = useTheme();
  const { username, logout } = useUser();
  const [showLogin, setShowLogin] = useState(false);

  const links = [
    { href: '/', label: t('home'), key: 'home' },
    { href: '/problems', label: t('problems'), key: 'problems' },
    { href: '/paths', label: t('paths'), key: 'paths' },
  ];

  const isActive = (href: string) => {
    if (href === '/') return pathname === '/';
    return pathname.startsWith(href);
  };

  const handleLogout = () => {
    logout();
    router.replace('/');
  };

  return (
    <>
      <nav
        className="sticky top-0 z-50"
        style={{
          backdropFilter: 'saturate(180%) blur(14px)',
          WebkitBackdropFilter: 'saturate(180%) blur(14px)',
          background: 'color-mix(in oklab, var(--bg) 82%, transparent)',
          borderBottom: '1px solid var(--line)',
        }}
      >
        <div className="max-w-[1280px] mx-auto px-7 h-14 flex items-center justify-between gap-6">
          <div className="flex items-center gap-8">
            <Link href="/" className="inline-flex items-center gap-2.5 font-semibold text-[15px] tracking-[-0.01em]">
              <FlameGlyph />
              Pyre Code
            </Link>
            <div className="flex items-center gap-0.5">
              {links.map((link) => (
                <Link
                  key={link.key}
                  href={link.href}
                  className={cn(
                    'px-2.5 py-1.5 rounded-lg text-[13.5px] transition-[background,color] duration-150',
                    isActive(link.href)
                      ? 'text-text bg-[color-mix(in_oklab,var(--text)_6%,transparent)]'
                      : 'text-text-2 hover:text-text hover:bg-[color-mix(in_oklab,var(--text)_5%,transparent)]'
                  )}
                >
                  {link.label}
                </Link>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            {solvedCount !== undefined && totalCount !== undefined && (
              <div
                className="inline-flex items-center gap-2 px-2.5 py-1 rounded-pill mono text-xs text-text-2"
                style={{
                  border: '1px solid var(--line)',
                  background: 'var(--bg-elev)',
                }}
              >
                <span
                  className="w-1.5 h-1.5 rounded-pill"
                  style={{
                    background: 'var(--easy)',
                    boxShadow: '0 0 0 3px color-mix(in oklab, var(--easy) 25%, transparent)',
                  }}
                />
                <span>{t('solvedCount', { solved: solvedCount, total: totalCount })}</span>
              </div>
            )}
            {username ? (
              <div className="flex items-center gap-1.5">
                <span className="inline-flex items-center gap-1.5 text-xs text-text-2">
                  <User className="w-3.5 h-3.5" />
                  {username}
                </span>
                <button
                  onClick={handleLogout}
                  className="w-8 h-8 inline-flex items-center justify-center rounded-lg text-text-2 cursor-pointer transition-[color,background,border-color] duration-150 hover:text-text hover:border-line-strong"
                  style={{
                    border: '1px solid var(--line)',
                    background: 'var(--bg-elev)',
                  }}
                  aria-label={t('logout')}
                  title={t('logout')}
                >
                  <LogOut className="w-3.5 h-3.5" />
                </button>
              </div>
            ) : (
              <button
                onClick={() => setShowLogin(true)}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs text-accent cursor-pointer transition-[background] duration-150 hover:bg-[color-mix(in_oklab,var(--accent)_8%,transparent)]"
                style={{
                  border: '1px solid var(--accent-line)',
                }}
              >
                <User className="w-3.5 h-3.5" />
                {t('login')}
              </button>
            )}
            <button
              onClick={toggleTheme}
              className="w-8 h-8 inline-flex items-center justify-center rounded-lg text-text-2 cursor-pointer transition-[color,background,border-color] duration-150 hover:text-text hover:border-line-strong"
              style={{
                border: '1px solid var(--line)',
                background: 'var(--bg-elev)',
              }}
              title="Toggle theme"
            >
              {theme === 'light' ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
            </button>
            <button
              onClick={() => setLocale(locale === 'en' ? 'zh' : 'en')}
              className="h-8 px-2 inline-flex items-center justify-center rounded-lg text-text-2 text-xs cursor-pointer transition-[color,background,border-color] duration-150 hover:text-text hover:border-line-strong"
              style={{
                border: '1px solid var(--line)',
                background: 'var(--bg-elev)',
              }}
              aria-label={`Switch language to ${locale === 'en' ? 'Chinese' : 'English'}`}
            >
              {locale === 'en' ? '中文' : 'EN'}
            </button>
          </div>
        </div>
      </nav>
      <AuthDialog open={showLogin} onClose={() => setShowLogin(false)} />
    </>
  );
}
