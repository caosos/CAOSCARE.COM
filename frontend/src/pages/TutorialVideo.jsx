import React, { useState } from "react";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Play, Video, Clapperboard } from "lucide-react";

/**
 * TutorialVideo — drop-in component for embedding short walkthrough videos
 * throughout the app. Designed to gracefully handle the case where a video
 * hasn't been recorded yet: it shows a clean placeholder card with the
 * script outline so reviewers and product owners know what's coming.
 */
export function TutorialVideo({ id, title, duration, src, poster, script, testid }) {
  const [open, setOpen] = useState(false);
  const hasVideo = Boolean(src);

  if (!open) {
    return (
      <Card
        className="p-3 border-caos-line bg-caos-ambient/30 inline-flex items-center gap-3 cursor-pointer hover:bg-caos-ambient transition-colors"
        onClick={() => setOpen(true)}
        data-testid={testid || `tutorial-${id}`}
      >
        <div className="w-10 h-10 rounded-full bg-caos-forest text-white flex items-center justify-center shrink-0">
          {hasVideo ? <Play className="w-4 h-4 ml-0.5" /> : <Clapperboard className="w-4 h-4" />}
        </div>
        <div>
          <p className="text-sm font-semibold text-caos-forest leading-tight">{title}</p>
          <p className="text-[10px] uppercase tracking-widest text-caos-mute">
            {hasVideo ? `Watch · ${duration || "60s"}` : `Coming soon · script ready`}
          </p>
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-4 border-caos-forest bg-white max-w-xl" data-testid={`${testid || `tutorial-${id}`}-open`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Video className="w-4 h-4 text-caos-forest" />
          <span className="font-semibold text-caos-forest">{title}</span>
        </div>
        <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>Close</Button>
      </div>
      {hasVideo ? (
        <video controls poster={poster} className="w-full rounded-lg bg-black" data-testid={`${testid || `tutorial-${id}`}-video`}>
          <source src={src} type="video/mp4" />
        </video>
      ) : (
        <div>
          <div className="aspect-video bg-caos-ambient/40 rounded-lg flex flex-col items-center justify-center text-caos-mute">
            <Clapperboard className="w-10 h-10 mb-2" />
            <p className="text-sm">Video being produced.</p>
          </div>
          {script && (
            <div className="mt-3 p-3 bg-caos-ambient/40 rounded text-xs text-caos-ink/80">
              <p className="font-bold uppercase tracking-widest text-caos-mute mb-2">Script preview</p>
              {script.split("\n").map((line, i) => <p key={i} className="leading-snug">{line}</p>)}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

export default TutorialVideo;
