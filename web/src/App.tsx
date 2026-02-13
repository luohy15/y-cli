import { useState, useCallback } from "react";
import { useAuth } from "./hooks/useAuth";
import Header from "./components/Header";
import ChatList from "./components/ChatList";
import ChatView from "./components/ChatView";

export default function App() {
  const auth = useAuth();
  const [selectedChatId, setSelectedChatId] = useState<string | null>(null);

  const handleSelectChat = useCallback((id: string | null) => {
    setSelectedChatId(id);
  }, []);

  const handleLogout = useCallback(() => {
    auth.logout();
    setSelectedChatId(null);
  }, [auth]);

  return (
    <div className="h-full flex flex-col">
      <Header email={auth.email} isLoggedIn={auth.isLoggedIn} gsiReady={auth.gsiReady} onLogout={handleLogout} />
      <div className="flex flex-1 min-h-0">
        <ChatList
          isLoggedIn={auth.isLoggedIn}
          selectedChatId={selectedChatId}
          onSelectChat={handleSelectChat}
        />
        <ChatView
          chatId={selectedChatId}
        />
      </div>
    </div>
  );
}
