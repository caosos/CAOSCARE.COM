import React, { useRef, useState } from "react";
import { api } from "../../lib/api";
import { Button } from "../ui/button";
import { Sparkles, X, Send } from "lucide-react";
import { executeUiActions } from "../../lib/adminAriaActions";
import CopyTranscriptButton from "../CopyTranscriptButton";

/**
 * Persistent admin configuration assistant - Aria embedded directly in
 * Community Administration (2026-08-27, per Michael's "administrator
 * should never need to understand entity IDs/adapters/HA" directive, and
 * "actively navigate/show, don't just describe"). Rendered once at the
 * Admin() root (not inside <Tabs>) so it survives every tab switch,
 * always knows the current section (see currentSection prop), and can
 * drive navigation/highlighting itself via onNavigate + the shared
 * AriaSpotlight overlay. Text-first by design - see
 * backend/routes/admin_assistant.py for why, and for the clean seam a
 * future voice frontend could reuse without rework.
 */
export default function AdminAria({ currentSection, onNavigate }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]); // [{role, content}]
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef(null);
  // One thread identity per panel session - every event this conversation
  // produces (backend routes.events) is grouped under it for later
  // reconstruction. Not persisted across a page reload; that's a real,
  // acceptable limit for this phase, not a silent gap (a reload starts a
  // genuinely new thread, which is honest).
  const conversationIdRef = useRef(`conv_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`);

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    const nextHistory = [...messages, { role: "user", content: text }];
    setMessages(nextHistory);
    setInput("");
    setBusy(true);
    try {
      const { data } = await api.post("/admin-assistant/chat", {
        message: text,
        history: messages, // prior turns only - the new one goes as `message`
        current_section: currentSection,
        conversation_id: conversationIdRef.current,
      });
      // Play the visual navigation/highlight sequence FIRST - the admin
      // should see Aria move through the screen before her explanation
      // lands, matching how a person would show-then-tell.
      await executeUiActions(data.ui_actions, { onNavigate });
      setMessages([...nextHistory, { role: "assistant", content: data.reply }]);
    } catch (err) {
      setMessages([...nextHistory, { role: "assistant", content: `Sorry - I hit an error: ${err?.response?.data?.detail || err.message}` }]);
    }
    setBusy(false);
    setTimeout(() => scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight }), 50);
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        data-testid="admin-aria-open"
        className="fixed bottom-6 right-6 z-40 flex items-center gap-2 rounded-full bg-caos-forest text-white px-5 py-3 shadow-lg hover:bg-caos-forest-hover"
      >
        <Sparkles className="w-5 h-5" /> Ask Aria
      </button>
    );
  }

  return (
    <div
      data-testid="admin-aria-panel"
      className="fixed bottom-6 right-6 z-40 w-[26rem] max-w-[calc(100vw-3rem)] h-[32rem] max-h-[calc(100vh-6rem)] bg-white border-2 border-caos-forest rounded-2xl shadow-2xl flex flex-col overflow-hidden"
    >
      <div className="flex items-center justify-between px-4 py-3 bg-caos-forest text-white shrink-0">
        <span className="flex items-center gap-2 font-display font-semibold"><Sparkles className="w-4 h-4" /> Ask Aria</span>
        <div className="flex items-center gap-3">
          <CopyTranscriptButton turns={messages} className="!text-white/80 hover:!text-white" />
          <button onClick={() => setOpen(false)} data-testid="admin-aria-close" aria-label="Close"><X className="w-5 h-5" /></button>
        </div>
      </div>
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3 text-sm">
        {messages.length === 0 && (
          <p className="text-caos-mute italic">
            Ask me to explain this screen, set up a room, or check the status of anything - I can inspect and configure the real system for you.
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-right" : "text-left"}>
            <div className={`inline-block rounded-xl px-3 py-2 max-w-[90%] whitespace-pre-wrap ${m.role === "user" ? "bg-caos-forest text-white" : "bg-caos-bone text-caos-ink"}`}>
              {m.content}
            </div>
          </div>
        ))}
        {busy && <div className="text-caos-mute italic">Aria is working…</div>}
      </div>
      <div className="flex items-center gap-2 p-3 border-t border-caos-line shrink-0">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
          placeholder="Ask Aria…"
          data-testid="admin-aria-input"
          className="flex-1 rounded-full border border-caos-line px-4 py-2 text-sm focus:outline-none focus:border-caos-forest"
        />
        <Button onClick={send} disabled={busy || !input.trim()} data-testid="admin-aria-send" className="bg-caos-forest rounded-full w-10 h-10 p-0">
          <Send className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
}
