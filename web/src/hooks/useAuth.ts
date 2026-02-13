import { useState, useEffect, useCallback } from "react";
import { API, getToken, setToken, clearToken, getStoredEmail } from "../api";

const GOOGLE_CLIENT_ID = (import.meta as any).env?.VITE_GOOGLE_CLIENT_ID || "";

export function useAuth() {
  const [email, setEmail] = useState<string | null>(getStoredEmail());
  const [isLoggedIn, setIsLoggedIn] = useState(!!getToken());

  const login = useCallback(async (credential: string) => {
    try {
      const res = await fetch(`${API}/auth/google`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id_token: credential }),
      });
      if (!res.ok) {
        console.error("Auth failed:", await res.text());
        return;
      }
      const data = await res.json();
      setToken(data.token);
      localStorage.setItem("user_email", data.email);
      setEmail(data.email);
      setIsLoggedIn(true);
    } catch (err) {
      console.error("Auth error:", err);
    }
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setEmail(null);
    setIsLoggedIn(false);
  }, []);

  // Expose handleGoogleCredential globally for GIS callback
  useEffect(() => {
    (window as any).handleGoogleCredential = (response: any) => {
      login(response.credential);
    };
    return () => {
      delete (window as any).handleGoogleCredential;
    };
  }, [login]);

  // Initialize Google Sign-In
  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return;
    const interval = setInterval(() => {
      if ((window as any).google?.accounts?.id) {
        clearInterval(interval);
        (window as any).google.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: (window as any).handleGoogleCredential,
        });
      }
    }, 100);
    return () => clearInterval(interval);
  }, []);

  return { email, isLoggedIn, login, logout };
}

export { GOOGLE_CLIENT_ID };
