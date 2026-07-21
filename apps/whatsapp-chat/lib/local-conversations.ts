// The standalone agent backend has no "list conversations" endpoint (by
// design - see docs/architecture/standalone-whatsapp-agent.md). This is a
// thin client-side convenience list, remembered per-browser, so the local
// test console feels like a real chat app across page reloads.
export interface LocalConversation {
  id: string;
  name: string;
  phone: string;
  lastMessage: string;
  updatedAt: string;
}

const STORAGE_KEY = "wa-chat-conversations";

export function loadConversations(): LocalConversation[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as LocalConversation[]) : [];
  } catch {
    return [];
  }
}

export function saveConversations(conversations: LocalConversation[]): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
}

export function upsertConversation(update: LocalConversation): LocalConversation[] {
  const current = loadConversations();
  const others = current.filter((c) => c.id !== update.id);
  const next = [update, ...others].sort(
    (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
  );
  saveConversations(next);
  return next;
}
