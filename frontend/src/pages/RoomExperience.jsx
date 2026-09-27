import React, { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { COMMUNITIES } from "../lib/roomExperience/communities";
import { availableFeatures, bedroomLabel, defaultSelection, formatSquareFeet } from "../lib/roomExperience/model";
import FloorPlanView from "../components/roomExperience/FloorPlanView";
import RoomFeatureConfigurator from "../components/roomExperience/RoomFeatureConfigurator";
import ExperiencePanel from "../components/roomExperience/ExperiencePanel";

// Public room experience (V1): community -> apartment model -> floor plan +
// square footage -> configure CAOSCare features -> experience the room.
// Data lives in lib/roomExperience/ (see communities.js for the demo/verified rules).

const eyebrow = "text-xs font-bold uppercase tracking-[0.22em] text-caos-mute mb-3";
const choice = (on) =>
  `text-left rounded-2xl border-2 p-5 transition-colors min-h-[64px] ${
    on ? "border-caos-forest bg-white" : "border-caos-line bg-white hover:border-caos-forest"
  }`;

export default function RoomExperience() {
  const [communityId, setCommunityId] = useState(COMMUNITIES[0]?.id);
  const community = COMMUNITIES.find((c) => c.id === communityId);
  const [modelId, setModelId] = useState(community?.models[0]?.id);
  const model = community?.models.find((m) => m.id === modelId) || community?.models[0];
  const features = useMemo(() => (model ? availableFeatures(model) : []), [model]);
  const [selected, setSelected] = useState(() => (model ? defaultSelection(model) : new Set()));

  const pickCommunity = (c) => { setCommunityId(c.id); pickModel(c.models[0]); };
  const pickModel = (m) => { setModelId(m.id); setSelected(defaultSelection(m)); };
  const toggle = (id) => setSelected((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });

  if (!community || !model) return null;
  return (
    <div className="min-h-screen bg-caos-bone" data-testid="room-experience">
      <nav className="flex items-center justify-between px-6 md:px-12 py-6 border-b border-caos-line">
        <Link to="/" className="text-2xl">
          <span className="font-display font-bold tracking-tighter text-caos-forest">CAOS</span>
          <span className="font-display font-light text-caos-forest">Care</span>
        </Link>
      </nav>

      <main className="px-6 md:px-12 py-14 max-w-7xl mx-auto space-y-16">
        <header className="max-w-3xl">
          <p className={eyebrow}>Room experience</p>
          <h1 className="font-display text-4xl md:text-6xl font-light tracking-tighter text-caos-forest">
            See your room with CAOSCare.
          </h1>
          <p className="text-lg text-caos-ink mt-5 leading-relaxed">
            Aria isn't another tablet for the resident. The room itself becomes the interface.
            Choose a community and an apartment, then see what CAOSCare adds to it.
          </p>
        </header>

        {community.dataStatus === "demo" && (
          <p role="note" className="rounded-2xl border-2 border-caos-terracotta bg-white px-5 py-4 text-caos-ink" data-testid="demo-data-notice">
            <b className="text-caos-terracotta">Demo data.</b> This community and its apartments are samples that show how
            the experience works. Real communities appear here only with their own published floor plans.
          </p>
        )}

        <section aria-labelledby="community-heading">
          <p className={eyebrow}>Step 1</p>
          <h2 id="community-heading" className="font-display text-2xl text-caos-forest mb-4">Choose a community</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {COMMUNITIES.map((c) => (
              <button key={c.id} type="button" aria-pressed={c.id === community.id}
                      className={choice(c.id === community.id)} onClick={() => pickCommunity(c)}>
                <span className="block font-display text-lg font-medium text-caos-forest">{c.name}</span>
                <span className="block text-sm text-caos-mute mt-1">{c.location}</span>
              </button>
            ))}
          </div>
        </section>

        <section aria-labelledby="model-heading">
          <p className={eyebrow}>Step 2</p>
          <h2 id="model-heading" className="font-display text-2xl text-caos-forest mb-4">Choose an apartment</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {community.models.map((m) => (
              <button key={m.id} type="button" aria-pressed={m.id === model.id} data-testid={`model-${m.id}`}
                      className={choice(m.id === model.id)} onClick={() => pickModel(m)}>
                <span className="block font-display text-lg font-medium text-caos-forest">{m.name}</span>
                <span className="block text-sm text-caos-mute mt-1">{bedroomLabel(m)} · {formatSquareFeet(m.squareFeet)}</span>
              </button>
            ))}
          </div>
        </section>

        <section aria-labelledby="configure-heading" className="grid grid-cols-1 lg:grid-cols-12 gap-10">
          <div className="lg:col-span-7">
            <p className={eyebrow}>Step 3</p>
            <h2 id="configure-heading" className="font-display text-2xl text-caos-forest">{model.name}</h2>
            <p className="text-caos-mute mb-4" data-testid="model-facts">
              {bedroomLabel(model)} · {formatSquareFeet(model.squareFeet)}
              {community.dataStatus === "demo" && " · demo figures"}
            </p>
            <FloorPlanView model={model} selected={selected} />
            {community.source && (
              <p className="text-xs text-caos-mute mt-2">
                Floor plan and square footage: {community.source.publisher}, retrieved {community.source.retrievedAt}.
              </p>
            )}
          </div>
          <div className="lg:col-span-5">
            <h3 className="font-display text-xl text-caos-forest mb-4 lg:mt-12">Choose CAOSCare features</h3>
            <RoomFeatureConfigurator features={features} selected={selected} onToggle={toggle} />
          </div>
        </section>

        <ExperiencePanel model={model} features={features} selected={selected} />
      </main>
    </div>
  );
}
