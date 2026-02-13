type BubbleRole = "user" | "assistant" | "tool" | "system";

const bubbleStyles: Record<BubbleRole, string> = {
  user: "self-end bg-blue-900/40 text-blue-100 rounded-br-sm",
  assistant: "self-start bg-neutral-800 text-neutral-300 rounded-bl-sm",
  tool: "self-start bg-neutral-900 text-neutral-400 border border-neutral-700 rounded-bl-sm text-xs",
  system: "self-center text-neutral-500 text-[0.7rem] py-1",
};

const labelStyles: Record<string, string> = {
  user: "text-blue-400",
  assistant: "text-violet-400",
  tool: "text-neutral-500",
};

const labelText: Record<string, string> = {
  user: "You",
  assistant: "Assistant",
  tool: "Tool",
};

interface MessageBubbleProps {
  role: BubbleRole;
  content: string;
  toolName?: string;
}

export default function MessageBubble({ role, content, toolName }: MessageBubbleProps) {
  if (role === "system") {
    return <div className={bubbleStyles.system}>{content}</div>;
  }

  return (
    <div
      className={`max-w-[85%] rounded-xl px-3.5 py-2.5 text-[0.825rem] leading-relaxed whitespace-pre-wrap break-words ${bubbleStyles[role]}`}
    >
      <div className={`text-[0.65rem] font-semibold uppercase tracking-wide mb-1 ${labelStyles[role]}`}>
        {labelText[role]}
        {toolName && role === "tool" && (
          <span className="ml-1.5 px-1.5 py-0.5 bg-neutral-800 rounded text-[0.65rem] text-violet-400">
            {toolName}
          </span>
        )}
      </div>
      <div>{content}</div>
    </div>
  );
}

export type { BubbleRole };
