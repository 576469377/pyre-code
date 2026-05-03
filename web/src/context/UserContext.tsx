'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface UserContextValue {
  username: string | null;
  login: (name: string) => void;
  logout: () => void;
}

const UserContext = createContext<UserContextValue>({
  username: null,
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

export function UserProvider({ children }: { children: ReactNode }) {
  const [username, setUsername] = useState<string | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem('pyre_username');
    if (saved) {
      setUsername(saved);
      setCookie('pyre_username', saved, 365);
    }
  }, []);

  const login = (name: string) => {
    const trimmed = name.trim();
    if (!trimmed) return;
    setUsername(trimmed);
    localStorage.setItem('pyre_username', trimmed);
    setCookie('pyre_username', trimmed, 365);
  };

  const logout = () => {
    setUsername(null);
    localStorage.removeItem('pyre_username');
    deleteCookie('pyre_username');
  };

  return (
    <UserContext.Provider value={{ username, login, logout }}>
      {children}
    </UserContext.Provider>
  );
}

export function useUser() {
  return useContext(UserContext);
}
