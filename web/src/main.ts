const API = window.location.origin;
let selectedChatId: string | null = null;
let eventSource: EventSource | null = null;

// --- Types ---
interface Chat {
  id: string;
  status: string;
  prompt?: string;
  created_at?: string;
}

interface ContentPart {
  type: string;
  text?: string;
}

interface MessageData {
  role?: string;
  content?: string | ContentPart[];
  tool?: string;
  arguments?: Record<string, unknown>;
}

interface EventData {
  data?: MessageData;
  role?: string;
  content?: string | ContentPart[];
  tool?: string;
  arguments?: Record<string, unknown>;
}

interface AskData {
  data?: { tool_name?: string; tool_args?: Record<string, unknown> };
  tool_name?: string;
  tool_args?: Record<string, unknown>;
}

type BubbleRole = "user" | "assistant" | "tool";

// --- Create Chat ---
async function createChat(): Promise<void> {
  const input = document.getElementById("prompt-input") as HTMLInputElement;
  const btn = document.getElementById("submit-btn") as HTMLButtonElement;
  const prompt = input.value.trim();
  if (!prompt) return;
  btn.disabled = true;
  try {
    await fetch(`${API}/v1/chats`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    });
    input.value = "";
    fetchChats();
  } finally {
    btn.disabled = false;
  }
}
(window as any).createChat = createChat;

document.getElementById("prompt-input")!.addEventListener("keydown", (e: KeyboardEvent) => {
  if (e.key === "Enter") createChat();
});

// --- List Chats ---
async function fetchChats(): Promise<void> {
  try {
    const res = await fetch(`${API}/v1/chats`);
    const chats: Chat[] = await res.json();
    renderChats(chats);
  } catch {
    document.getElementById("chats-list")!.innerHTML =
      '<p class="text-neutral-500 italic text-sm p-3">Error loading chats</p>';
  }
}

function renderChats(chats: Chat[]): void {
  const container = document.getElementById("chats-list")!;
  if (!chats.length) {
    container.innerHTML =
      '<p class="text-neutral-500 italic text-sm p-3">No chats yet</p>';
    return;
  }
  container.innerHTML = chats
    .map((c) => {
      const sel = c.id === selectedChatId ? " ring-1 ring-blue-400 bg-neutral-800/50" : "";
      const time = c.created_at
        ? new Date(c.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
        : "";
      return `<div class="flex items-center gap-2 px-3 py-2 rounded-md cursor-pointer hover:bg-neutral-800 transition-colors${sel}"
                   onclick="selectChat('${c.id}', this)">
        <span class="badge-${c.status} shrink-0 px-1.5 py-0.5 rounded-full text-[0.6rem] font-semibold uppercase">${c.status}</span>
        <span class="flex-1 truncate text-sm">${esc(c.prompt || "")}</span>
        <span class="text-[0.65rem] text-neutral-500 shrink-0">${time}</span>
      </div>`;
    })
    .join("");
}

function esc(s: string): string {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

// --- Chat view ---
function selectChat(id: string, el?: HTMLElement): void {
  if (selectedChatId === id) {
    selectedChatId = null;
    closeEventSource();
    document.getElementById("chat-container")!.classList.add("hidden");
    document.getElementById("chat-container")!.classList.remove("flex");
    document.getElementById("chat-placeholder")!.classList.remove("hidden");
    document.getElementById("approval-bar")!.classList.add("hidden");
    document.getElementById("approval-bar")!.classList.remove("flex");
    document.querySelectorAll("#chats-list > div").forEach((e) => {
      e.classList.remove("ring-1", "ring-blue-400", "bg-neutral-800/50");
    });
    return;
  }
  selectedChatId = id;
  document.querySelectorAll("#chats-list > div").forEach((e) => {
    e.classList.remove("ring-1", "ring-blue-400", "bg-neutral-800/50");
  });
  if (el) el.classList.add("ring-1", "ring-blue-400", "bg-neutral-800/50");

  const chat = document.getElementById("chat-container")!;
  chat.innerHTML = "";
  chat.classList.remove("hidden");
  chat.classList.add("flex");
  document.getElementById("chat-placeholder")!.classList.add("hidden");
  document.getElementById("approval-bar")!.classList.add("hidden");
  document.getElementById("approval-bar")!.classList.remove("flex");

  closeEventSource();
  eventSource = new EventSource(`${API}/v1/chats/${id}/events`);

  eventSource.addEventListener("message", (e) => handleMessageEvent(chat, e.data));
  for (const t of ["text", "tool_use", "tool_result"]) {
    eventSource.addEventListener(t, (e) => handleMessageEvent(chat, (e as MessageEvent).data));
  }
  eventSource.addEventListener("ask", (e) => handleAskEvent(chat, (e as MessageEvent).data));
  eventSource.addEventListener("waiting_approval", (e) => handleAskEvent(chat, (e as MessageEvent).data));
  eventSource.addEventListener("done", () => {
    addSystemBubble(chat, "Chat completed");
    closeEventSource();
    fetchChats();
  });
  eventSource.addEventListener("error", () => {});
}
(window as any).selectChat = selectChat;

function handleMessageEvent(chat: HTMLElement, raw: string): void {
  try {
    const evt: EventData = JSON.parse(raw);
    const msg = evt.data || evt;
    const role = msg.role || "assistant";
    const content = extractContent(msg.content);
    const tool = msg.tool;

    if (role === "user") {
      addBubble(chat, "user", content);
    } else if (tool) {
      const body = msg.arguments
        ? `${tool}\n${formatArgs(msg.arguments)}`
        : `${tool}\n${truncate(content, 500)}`;
      addBubble(chat, "tool", body, tool);
    } else {
      addBubble(chat, "assistant", content);
    }
  } catch {}
}

function handleAskEvent(chat: HTMLElement, raw: string): void {
  try {
    const evt: AskData = JSON.parse(raw);
    const data = evt.data || evt;
    const toolName = data.tool_name || "";
    const args = data.tool_args || {};
    addBubble(chat, "tool", `${toolName}\n${formatArgs(args)}`, toolName);
    document.getElementById("approval-bar")!.classList.remove("hidden");
    document.getElementById("approval-bar")!.classList.add("flex");
  } catch {}
}

function extractContent(content?: string | ContentPart[]): string {
  if (!content) return "";
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .map((p) => {
        if (typeof p === "string") return p;
        if (p.type === "text") return p.text || "";
        if (p.type === "image") return "[image]";
        return "";
      })
      .join("");
  }
  return String(content);
}

function formatArgs(args: unknown): string {
  if (!args || typeof args !== "object") return "";
  try {
    return JSON.stringify(args, null, 2);
  } catch {
    return String(args);
  }
}

function truncate(s: string, n: number): string {
  if (!s) return "";
  return s.length > n ? s.slice(0, n) + "..." : s;
}

// Bubble classes by role
const bubbleStyles: Record<BubbleRole, string> = {
  user: "self-end bg-blue-900/40 text-blue-100 rounded-br-sm",
  assistant: "self-start bg-neutral-800 text-neutral-300 rounded-bl-sm",
  tool: "self-start bg-neutral-900 text-neutral-400 border border-neutral-700 rounded-bl-sm text-xs",
};

const labelStyles: Record<BubbleRole, string> = {
  user: "text-blue-400",
  assistant: "text-violet-400",
  tool: "text-neutral-500",
};

function addBubble(chat: HTMLElement, role: BubbleRole, text: string, toolName?: string): void {
  const row = document.createElement("div");
  row.className = `max-w-[85%] rounded-xl px-3.5 py-2.5 text-[0.825rem] leading-relaxed whitespace-pre-wrap break-words ${bubbleStyles[role]}`;

  // Label
  const lbl = document.createElement("div");
  lbl.className = `text-[0.65rem] font-semibold uppercase tracking-wide mb-1 ${labelStyles[role]}`;
  lbl.textContent = role === "user" ? "You" : role === "assistant" ? "Assistant" : "Tool";
  if (toolName && role === "tool") {
    const tn = document.createElement("span");
    tn.className = "ml-1.5 px-1.5 py-0.5 bg-neutral-800 rounded text-[0.65rem] text-violet-400";
    tn.textContent = toolName;
    lbl.appendChild(tn);
  }
  row.appendChild(lbl);

  const body = document.createElement("div");
  body.textContent = text;
  row.appendChild(body);

  chat.appendChild(row);
  chat.scrollTop = chat.scrollHeight;
}

function addSystemBubble(chat: HTMLElement, text: string): void {
  const row = document.createElement("div");
  row.className = "self-center text-neutral-500 text-[0.7rem] py-1";
  row.textContent = text;
  chat.appendChild(row);
  chat.scrollTop = chat.scrollHeight;
}

function closeEventSource(): void {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
}

// --- Approval ---
async function approve(approved: boolean): Promise<void> {
  if (!selectedChatId) return;
  document.getElementById("approval-bar")!.classList.add("hidden");
  document.getElementById("approval-bar")!.classList.remove("flex");
  await fetch(`${API}/v1/chats/${selectedChatId}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved }),
  });
  fetchChats();
}
(window as any).approve = approve;

// --- Polling ---
fetchChats();
setInterval(fetchChats, 5000);
