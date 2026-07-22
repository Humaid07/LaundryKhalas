"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api-client";
import {
  loadConversations,
  upsertConversation,
  type LocalConversation,
} from "@/lib/local-conversations";
import { formatDateSeparator, isSameDay } from "@/lib/formatters";
import type { Message, MessageAction, SettingsStatus, TestChatResponse } from "@/lib/types";
import { Sidebar } from "@/components/Sidebar";
import { ChatHeader } from "@/components/ChatHeader";
import { ModeBanner } from "@/components/ModeBanner";
import { MessageBubble } from "@/components/MessageBubble";
import { DateSeparator } from "@/components/DateSeparator";
import { Composer } from "@/components/Composer";
import { TypingIndicator } from "@/components/TypingIndicator";
import { DebugPanel } from "@/components/DebugPanel";
import { EmptyState } from "@/components/EmptyState";
import { ErrorBanner } from "@/components/ErrorBanner";

const DEFAULT_NAME = "Test Customer";
const DEFAULT_PHONE = "+971500000000";

// Fallbacks if the backend settings aren't loaded yet. The real values come
// from /api/settings/status (AGENT_MIN/MAX_TYPING_DELAY_MS), so the humanized
// delay is configurable without a frontend change.
const FALLBACK_MIN_TYPING_MS = 2000;
const FALLBACK_MAX_TYPING_MS = 3000;

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export default function ChatPage() {
  const [conversations, setConversations] = useState<LocalConversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [agentTyping, setAgentTyping] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastResponse, setLastResponse] = useState<TestChatResponse | null>(null);
  const [debugOpen, setDebugOpen] = useState(false);
  const [settingsStatus, setSettingsStatus] = useState<SettingsStatus | null>(null);

  const [newName, setNewName] = useState(DEFAULT_NAME);
  const [newPhone, setNewPhone] = useState(DEFAULT_PHONE);

  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setConversations(loadConversations());
    api
      .getSettingsStatus()
      .then(setSettingsStatus)
      .catch(() => setSettingsStatus(null));
  }, []);

  useEffect(() => {
    if (!activeId) {
      setMessages([]);
      return;
    }
    setMessagesLoading(true);
    setError(null);
    api
      .getMessages(activeId)
      .then(setMessages)
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.detail : "Could not load messages.");
      })
      .finally(() => setMessagesLoading(false));
  }, [activeId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, agentTyping]);

  const activeConversation = conversations.find((c) => c.id === activeId) ?? null;
  const headerName = activeConversation?.name ?? newName;
  const headerPhone = activeConversation?.phone ?? newPhone;

  const handleNewChat = () => {
    setActiveId(null);
    setMessages([]);
    setError(null);
    setLastResponse(null);
    setNewName(DEFAULT_NAME);
    setNewPhone(DEFAULT_PHONE);
  };

  const handleSend = async (text: string, actionId?: string) => {
    setSending(true);
    setError(null);

    // 1. Show the customer's own message immediately (optimistic bubble).
    const optimistic: Message = {
      id: `local-${Date.now()}`,
      conversation_id: activeId ?? "pending",
      direction: "inbound",
      sender_type: "customer",
      text,
      domain_status: null,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimistic]);

    // 2. Show the agent typing bubble for a natural, configurable delay.
    setAgentTyping(true);
    const min = settingsStatus?.agent_min_typing_delay_ms ?? FALLBACK_MIN_TYPING_MS;
    const max = settingsStatus?.agent_max_typing_delay_ms ?? FALLBACK_MAX_TYPING_MS;
    const target = min + Math.random() * Math.max(0, max - min);
    const startedAt = Date.now();

    try {
      const response = await api.sendTestMessage({
        conversation_id: activeId ?? undefined,
        sender_name: activeConversation?.name ?? newName,
        phone_number: activeConversation?.phone ?? newPhone,
        message: text,
        action_id: actionId,
      });

      setLastResponse(response);

      const updated = upsertConversation({
        id: response.conversation_id,
        name: activeConversation?.name ?? (newName || DEFAULT_NAME),
        phone: activeConversation?.phone ?? newPhone,
        lastMessage: response.agent_reply,
        updatedAt: new Date().toISOString(),
      });
      setConversations(updated);
      setActiveId(response.conversation_id);

      const fresh = await api.getMessages(response.conversation_id);
      // The interactive action buttons live on the just-generated reply
      // only (see lib/types.ts) - GET /api/messages doesn't persist them,
      // so attach them here onto the last (agent) message before render.
      if (response.actions.length > 0 && fresh.length > 0) {
        fresh[fresh.length - 1] = {
          ...fresh[fresh.length - 1],
          actions: response.actions,
        };
      }

      // 3. Keep the typing bubble up for at least the minimum delay even if
      //    the backend replied quickly; if it was slow, we've already waited.
      const elapsed = Date.now() - startedAt;
      if (elapsed < target) await sleep(target - elapsed);

      setAgentTyping(false);
      setMessages(fresh);
    } catch (err) {
      setAgentTyping(false);
      // Drop the optimistic bubble again on failure so it isn't left dangling.
      setMessages((prev) => prev.filter((m) => m.id !== optimistic.id));
      setError(err instanceof ApiError ? err.detail : "Could not send message.");
    } finally {
      setSending(false);
    }
  };

  const handleActionClick = (action: MessageAction) => {
    handleSend(action.label, action.id);
  };

  return (
    <div className="flex h-screen w-full flex-col">
      <ModeBanner status={settingsStatus} />
      <div className="flex min-h-0 flex-1">
        <Sidebar
          conversations={conversations}
          activeId={activeId}
          onSelect={setActiveId}
          onNewChat={handleNewChat}
        />

        <main className="flex min-w-0 flex-1 flex-col">
          <ChatHeader
            name={headerName}
            phone={headerPhone}
            editable={!activeId}
            onNameChange={setNewName}
            onPhoneChange={setNewPhone}
            debugOpen={debugOpen}
            onToggleDebug={() => setDebugOpen((v) => !v)}
          />

          {error && <ErrorBanner message={error} />}

          <div className="wa-chat-bg scrollbar-thin flex-1 overflow-y-auto px-6 py-4">
            {messagesLoading ? (
              <div className="flex h-full items-center justify-center text-sm text-wa-muted">
                Loading messages…
              </div>
            ) : messages.length === 0 ? (
              <EmptyState
                title="Say hello to LaundryKhalas"
                description='Try: "Hi" or "I need laundry pickup tomorrow"'
              />
            ) : (
              <div className="space-y-1.5">
                {messages.map((message, i) => {
                  const prev = messages[i - 1];
                  const showDate = !prev || !isSameDay(prev.created_at, message.created_at);
                  return (
                    <div key={message.id}>
                      {showDate && <DateSeparator label={formatDateSeparator(message.created_at)} />}
                      <MessageBubble
                        message={message}
                        onActionClick={handleActionClick}
                        actionsDisabled={sending}
                      />
                    </div>
                  );
                })}
                {agentTyping && <TypingIndicator />}
                <div ref={bottomRef} />
              </div>
            )}
          </div>

          <Composer disabled={sending} onSend={handleSend} />
        </main>

        {debugOpen && <DebugPanel last={lastResponse} />}
      </div>
    </div>
  );
}
