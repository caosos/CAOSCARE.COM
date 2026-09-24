/**
 * Browser media priming for the room page - moved verbatim out of
 * Kiosk.jsx (2026-09-23) so the page could take on the wake-word hook
 * without growing. Behavior unchanged.
 *
 * Prime browser audio + mic permission on the first user click.
 * Without a user gesture, Chrome will silently block both TTS playback and getUserMedia.
 * Note: when running inside a cross-origin iframe (e.g. the Emergent preview pane),
 * Chrome rejects getUserMedia synchronously unless the parent tag sets
 * allow="microphone". We detect that case and offer a "open in full tab" escape.
 */
import { useRef, useState } from "react";
import { toast } from "sonner";

export const inSandboxedIframe = () => {
  try { return window.self !== window.top; } catch { return true; }
};

export const openInFullTab = () => {
  try { window.open(window.location.href, "_blank", "noopener"); } catch { /* ignore */ }
};

export function useKioskMediaPrime() {
  const [micReady, setMicReady] = useState(false);       // user gesture received + mic permission granted
  const audioCtxRef = useRef(null);

  const primeMedia = async () => {
    if (micReady) return true;
    try {
      // Unlock AudioContext for playback (announcements, RealtimeChatScreen audio)
      if (!audioCtxRef.current) {
        const Ctx = window.AudioContext || window.webkitAudioContext;
        audioCtxRef.current = new Ctx();
        if (audioCtxRef.current.state === "suspended") await audioCtxRef.current.resume();
      }
      // Ask for mic access and immediately release the stream (Realtime's own
      // WebRTC setup re-acquires it when the call actually starts)
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((t) => t.stop());
      setMicReady(true);
      return true;
    } catch (e) {
      // Iframe sandbox = no prompt, direct NotAllowedError. Give the user a way out.
      if (inSandboxedIframe()) {
        toast.error("This preview frame can't ask for your mic. Tap to open in a full tab.", {
          duration: 8000,
          action: { label: "Open full tab", onClick: openInFullTab },
        });
      } else {
        toast.error("Microphone permission needed. Please allow it in your browser.");
      }
      return false;
    }
  };

  return { micReady, primeMedia };
}
