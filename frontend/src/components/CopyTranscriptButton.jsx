import React, { useState } from "react";
import { Copy, Check } from "lucide-react";
import { toast } from "sonner";

/**
 * One shared "copy this conversation" control - reused by every place a
 * transcript is rendered (resident voice history, operator Aria past
 * conversations, live Admin Aria chat) instead of each view reimplementing
 * clipboard logic. Accepts the view's own turns array as-is; `getLine`
 * lets each call site map its own field names (content vs text) to one
 * plain-text line without this component needing to know their shape.
 */
export default function CopyTranscriptButton({ turns, label = "Copy", className = "", getLine }) {
  const [copied, setCopied] = useState(false);

  if (!turns || turns.length === 0) return null;

  const copy = async () => {
    const text = turns.map(getLine || defaultLine).join("\n");
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      toast.success("Conversation copied");
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("Couldn't copy — clipboard access blocked");
    }
  };

  return (
    <button
      onClick={copy}
      className={`inline-flex items-center gap-1 text-xs font-semibold text-caos-mute hover:text-caos-forest transition-colors ${className}`}
      data-testid="copy-transcript-btn"
      title="Copy this conversation"
      type="button"
    >
      {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
      {copied ? "Copied" : label}
    </button>
  );
}

function defaultLine(t) {
  const who = t.role === "assistant" ? "Aria" : "Resident";
  return `${who}: ${t.text ?? t.content ?? ""}`;
}
