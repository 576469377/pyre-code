const DRAFT_KEY_PREFIX = 'pyre-code-draft:';

function getDraftKey(username: string, problemId: string) {
  return `${DRAFT_KEY_PREFIX}${encodeURIComponent(username)}:${problemId}`;
}

export function loadCodeDraft(username: string, problemId: string): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage.getItem(getDraftKey(username, problemId));
  } catch {
    return null;
  }
}

export function saveCodeDraft(username: string, problemId: string, code: string) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(getDraftKey(username, problemId), code);
  } catch {
    // Ignore storage write failures (private mode, quota, etc).
  }
}
