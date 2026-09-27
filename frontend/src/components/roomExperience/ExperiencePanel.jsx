import React from "react";
import { ExperienceVideo } from "../landing/ExperienceVideoLibrary";
import { EXPERIENCE_VIDEOS } from "../../lib/experienceVideos";
import StatusPill from "../capabilities/StatusPill";

// "Experience this room with CAOSCare": what the resident would say for each
// switched-on feature, plus the resident-experience video library. Later
// phases (conversational setup, generated room previews) plug in here.

export default function ExperiencePanel({ model, features, selected }) {
  const chosen = features.filter((f) => selected.has(f.id));
  const video = EXPERIENCE_VIDEOS[0];
  return (
    <section aria-labelledby="experience-heading" data-testid="experience-panel">
      <p className="text-xs font-bold uppercase tracking-[0.22em] text-caos-mute mb-3">Step 4</p>
      <h2 id="experience-heading" className="font-display text-3xl md:text-4xl font-light tracking-tight text-caos-forest">
        Experience this room with CAOSCare
      </h2>
      <p className="text-lg text-caos-ink mt-3 max-w-2xl">
        In the {model.name.replace(/\s*\(sample\)/i, "")}, the room itself is the interface. The resident simply says:
      </p>
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 mt-8">
        <ul className="lg:col-span-5 space-y-3" data-testid="experience-phrases">
          {chosen.length === 0 && (
            <li className="text-caos-mute">Switch on a feature above to see how it would sound.</li>
          )}
          {chosen.map((f) => (
            <li key={f.id} className="bg-white rounded-2xl border border-caos-line p-4">
              <p className="font-display text-xl text-caos-forest">“{f.phrase}”</p>
              <p className="flex flex-wrap items-center gap-2 mt-2 text-sm text-caos-mute">
                {f.label} <StatusPill status={f.status} />
              </p>
            </li>
          ))}
        </ul>
        {video && (
          <div className="lg:col-span-7">
            <ExperienceVideo video={video} featured />
          </div>
        )}
      </div>
    </section>
  );
}
