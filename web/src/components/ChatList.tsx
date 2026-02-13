import { useState, useEffect, useCallback } from "react";
import { API, authFetch, clearToken } from "../api";

interface Chat {
  id: string;
  status: string;
  prompt?: string;
  created_at?: string;
}

interface ChatListProps {
  isLoggedIn: boolean;
  selectedChatId: string | null;
  onSelectChat: (id: string | null) => void;
  refreshKey: number;
  onChatCreated: () => void;
}

export default function ChatList({ isLoggedIn, selectedChatId, onSelectChat, refreshKey, onChatCreated }: ChatListProps) {
  const [chats, setChats] = useState<Chat[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [sending, setSending] = useState(false);

  const fetchChats = useCallback(async () => {
    if (!isLoggedIn) {
      setChats([]);
      setLoading(false);
      return;
    }
    try {
      const res = await authFetch(`${API}/v1/chats`);
      if (res.status === 401) {
        clearToken();
        return;
      }
      const data: Chat[] = await res.json();
      setChats(data);
      setError(false);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [isLoggedIn]);

  useEffect(() => {
    fetchChats();
  }, [fetchChats, refreshKey]);

  // Poll every 5s
  useEffect(() => {
    if (!isLoggedIn) return;
    const id = setInterval(fetchChats, 5000);
    return () => clearInterval(id);
  }, [isLoggedIn, fetchChats]);

  const createChat = async () => {
    const trimmed = prompt.trim();
    if (!trimmed) return;
    setSending(true);
    try {
      await authFetch(`${API}/v1/chats`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: trimmed }),
      });
      setPrompt("");
      onChatCreated();
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") createChat();
  };

  const handleClick = (id: string) => {
    onSelectChat(selectedChatId === id ? null : id);
  };

  return (
    <div className="w-80 min-w-[260px] border-r border-neutral-800 flex flex-col shrink-0">
      <div className="flex gap-2 p-3 border-b border-neutral-800">
        <input
          type="text"
          placeholder="New chat..."
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={handleKeyDown}
          className="flex-1 px-2.5 py-1.5 bg-neutral-900 border border-neutral-700 rounded-md text-sm text-neutral-200 outline-none focus:border-blue-400"
          autoFocus
        />
        <button
          onClick={createChat}
          disabled={sending}
          className="px-3.5 py-1.5 bg-blue-400 text-neutral-950 rounded-md text-sm font-semibold cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Send
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {!isLoggedIn ? (
          <p className="text-neutral-500 italic text-sm p-3">Sign in to view chats</p>
        ) : loading ? (
          <p className="text-neutral-500 italic text-sm p-3">Loading...</p>
        ) : error ? (
          <p className="text-neutral-500 italic text-sm p-3">Error loading chats</p>
        ) : chats.length === 0 ? (
          <p className="text-neutral-500 italic text-sm p-3">No chats yet</p>
        ) : (
          chats.map((c) => {
            const sel = c.id === selectedChatId;
            const time = c.created_at
              ? new Date(c.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
              : "";
            return (
              <div
                key={c.id}
                onClick={() => handleClick(c.id)}
                className={`flex items-center gap-2 px-3 py-2 rounded-md cursor-pointer hover:bg-neutral-800 transition-colors ${
                  sel ? "ring-1 ring-blue-400 bg-neutral-800/50" : ""
                }`}
              >
                <span className={`badge-${c.status} shrink-0 px-1.5 py-0.5 rounded-full text-[0.6rem] font-semibold uppercase`}>
                  {c.status}
                </span>
                <span className="flex-1 truncate text-sm">{c.prompt || ""}</span>
                <span className="text-[0.65rem] text-neutral-500 shrink-0">{time}</span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
