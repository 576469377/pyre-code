'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useProblemStore } from '@/store/problemStore';

interface UserContextValue {
  username: string | null;
  isReady: boolean;
  login: (name: string) => void;
  logout: () => void;
}

const UserContext = createContext<UserContextValue>({
  username: null,
  isReady: false,
  login: () => {},
  logout: () => {},
});

function setCookie(name: string, value: string, days: number) {
  const expires = new Date(Date.now() + days * 864e5).toUTCString();
  document.cookie = `${name}=${encodeURIComponent(value)};expires=${expires};path=/`;
}

function deleteCookie(name: string) {
  document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/`;
}

function resetWorkspaceState() {
  useProblemStore.setState({
    currentCode: '',
    submissionResult: null,
    isSubmitting: false,
    drawerOpen: false,
    bottomTab: 'testcases',
    selectedCaseIndex: 0,
    customTests: [],
    isRunning: false,
    runResult: null,
    submissionHistory: [],
    aiHelpConfigOpen: false,
    aiHelpCustomPrompt: '',
    aiHelpResponse: null,
    aiHelpError: null,
    aiHelpLoading: false,
  });
}

export function UserProvider({ children }: { children: ReactNode }) {
  const [username, setUsername] = useState<string | null>(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem('pyre_username');
    if (saved) {
      setUsername(saved);
      setCookie('pyre_username', saved, 365);
    }
    setIsReady(true);
  }, []);

  const login = (name: string) => {
    const trimmed = name.trim();
    if (!trimmed) return;
    resetWorkspaceState();
    setUsername(trimmed);
    localStorage.setItem('pyre_username', trimmed);
    setCookie('pyre_username', trimmed, 365);
  };

  const logout = () => {
    resetWorkspaceState();
    setUsername(null);
    localStorage.removeItem('pyre_username');
    deleteCookie('pyre_username');
  };

  return (
    <UserContext.Provider value={{ username, isReady, login, logout }}>
      {children}
    </UserContext.Provider>
  );
}

export function useUser() {
  return useContext(UserContext);
}
