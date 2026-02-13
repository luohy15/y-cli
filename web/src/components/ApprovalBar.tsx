import { useCallback } from "react";
import { API, authFetch } from "../api";

interface ApprovalBarProps {
  chatId: string;
  visible: boolean;
  onApproved: () => void;
}

export default function ApprovalBar({ chatId, visible, onApproved }: ApprovalBarProps) {
  const approve = useCallback(async (approved: boolean) => {
    await authFetch(`${API}/v1/chats/${chatId}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approved }),
    });
    onApproved();
  }, [chatId, onApproved]);

  if (!visible) return null;

  return (
    <div className="px-6 py-3 border-t border-neutral-800 flex items-center gap-2">
      <span className="text-sm text-yellow-400 mr-2">Tool requires approval</span>
      <button
        onClick={() => approve(true)}
        className="px-3 py-1.5 bg-green-400 text-neutral-950 rounded-md text-sm font-semibold cursor-pointer"
      >
        Approve
      </button>
      <button
        onClick={() => approve(false)}
        className="px-3 py-1.5 bg-red-400 text-neutral-950 rounded-md text-sm font-semibold cursor-pointer"
      >
        Deny
      </button>
    </div>
  );
}
