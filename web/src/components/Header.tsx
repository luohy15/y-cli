import { useEffect, useRef } from "react";
import { GOOGLE_CLIENT_ID } from "../hooks/useAuth";

interface HeaderProps {
  email: string | null;
  isLoggedIn: boolean;
  onLogout: () => void;
}

export default function Header({ email, isLoggedIn, onLogout }: HeaderProps) {
  const signinRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isLoggedIn || !GOOGLE_CLIENT_ID || !signinRef.current) return;
    const interval = setInterval(() => {
      if ((window as any).google?.accounts?.id && signinRef.current) {
        clearInterval(interval);
        (window as any).google.accounts.id.renderButton(signinRef.current, {
          theme: "filled_black",
          size: "medium",
          shape: "pill",
        });
      }
    }, 100);
    return () => clearInterval(interval);
  }, [isLoggedIn]);

  return (
    <header className="px-6 py-4 border-b border-neutral-800 shrink-0 flex items-center justify-between">
      <h1 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-violet-400 bg-clip-text text-transparent inline">
        yovy
      </h1>
      <div className="flex items-center gap-3">
        {isLoggedIn ? (
          <div className="flex items-center gap-2">
            <span className="text-sm text-neutral-400">{email}</span>
            <button
              onClick={onLogout}
              className="px-2.5 py-1 bg-neutral-800 border border-neutral-700 text-neutral-400 rounded-md text-xs cursor-pointer hover:bg-neutral-700 hover:text-neutral-200"
            >
              Logout
            </button>
          </div>
        ) : (
          <div ref={signinRef} />
        )}
      </div>
    </header>
  );
}
