import { useState } from "react";
import { Send } from "lucide-react";
import { useAskAria } from "./WorkspaceShell";

// Ask Aria box: the question goes to the existing Admin Aria assistant
// (/admin-assistant/chat) and the answer appears in its panel.
export default function AriaBox() {
  const { openAria } = useAskAria();
  const [text, setText] = useState("");
  const ask = () => { if (text.trim()) { openAria(text.trim()); setText(""); } else { openAria(); } };
  return (
    <div className="mt-2 space-y-3" data-testid="ws-aria-box">
      <p className="text-[15px] text-[#4B5563]">Ask about anything in CAOSCare — Aria checks the real records.</p>
      <div className="flex items-center gap-2 rounded-lg border border-[#E5E7EB] bg-white px-3 py-2">
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask Aria…" aria-label="Ask Aria"
               onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); ask(); } }}
               className="w-full bg-transparent text-[15px] outline-none" data-testid="ws-aria-input" />
        <button type="button" onClick={ask} aria-label="Send to Aria" className="text-[#1D72D8]"><Send className="h-4 w-4" /></button>
      </div>
    </div>
  );
}
