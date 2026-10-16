import React, { useMemo, useState } from "react";
import { COMMUNITIES } from "../lib/roomExperience/communities";
import { availableFeatures, bedroomLabel, defaultSelection, formatSquareFeet } from "../lib/roomExperience/model";
import FloorPlanView from "../components/roomExperience/FloorPlanView";
import RoomFeatureConfigurator from "../components/roomExperience/RoomFeatureConfigurator";
import ExperiencePanel from "../components/roomExperience/ExperiencePanel";
import { CAPABILITIES_BY_ID } from "../lib/capabilities";
import CapabilityPanel from "../components/capabilities/CapabilityPanel";
import useCapabilityPanel from "../components/capabilities/useCapabilityPanel";
import PublicPage from "../components/public/PublicPage";

// Public room experience (V1): community -> apartment model -> floor plan +
// square footage -> configure CAOSCare features -> experience the room.
// Data lives in lib/roomExperience/ (see communities.js for the demo/verified rules).

const eyebrow = "text-[13px] font-semibold uppercase tracking-[0.14em] text-[#2F80ED] mb-2";
const choice = (on) =>
  `text-left rounded-xl border-2 p-5 transition-colors min-h-[64px] ${
    on ? "border-[#2F80ED] bg-[#EFF6FF]" : "border-[#E5E7EB] bg-white hover:border-[#2F80ED]"
  }`;

export default function RoomExperience() {
  const [communityId, setCommunityId] = useState(COMMUNITIES[0]?.id);
  const community = COMMUNITIES.find((c) => c.id === communityId);
  const [modelId, setModelId] = useState(community?.models[0]?.id);
  const model = community?.models.find((m) => m.id === modelId) || community?.models[0];
  const features = useMemo(() => (model ? availableFeatures(model) : []), [model]);
  const [selected, setSelected] = useState(() => (model ? defaultSelection(model) : new Set()));
  const panel = useCapabilityPanel(CAPABILITIES_BY_ID);

  const pickCommunity = (c) => { setCommunityId(c.id); pickModel(c.models[0]); };
  const pickModel = (m) => { setModelId(m.id); setSelected(defaultSelection(m)); };
  const toggle = (id) => setSelected((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });

  if (!community || !model) return null;
  return (
    <PublicPage testid="room-experience">
      <main className="mx-auto max-w-7xl space-y-16 px-4 py-12 sm:px-6 lg:px-8">
        <header className="max-w-3xl">
          <p className={eyebrow}>Room experience</p>
          <h1 className="text-[34px] font-bold leading-[1.1] tracking-tight text-[#111827] sm:text-[46px]">
            See your room with CAOSCare.
          </h1>
          <p className="text-lg text-[#111827] mt-5 leading-relaxed">
            Aria isn't another tablet for the resident. The room itself becomes the interface.
            Choose a community and an apartment, then see what CAOSCare adds to it.
          </p>
        </header>

        {community.dataStatus === "demo" && (
          <p role="note" className="rounded-xl border border-[#FDE68A] bg-[#FFFBEB] px-5 py-4 text-[#111827]" data-testid="demo-data-notice">
            <b className="text-[#B45309]">Demo data.</b> This community and its apartments are samples that show how
            the experience works. Real communities appear here only with their own published floor plans.
          </p>
        )}

        <section aria-labelledby="community-heading">
          <p className={eyebrow}>Step 1</p>
          <h2 id="community-heading" className="text-[24px] font-bold tracking-tight text-[#111827] mb-4">Choose a community</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {COMMUNITIES.map((c) => (
              <button key={c.id} type="button" aria-pressed={c.id === community.id}
                      className={choice(c.id === community.id)} onClick={() => pickCommunity(c)}>
                <span className="block text-lg font-medium text-[#111827]">{c.name}</span>
                <span className="block text-sm text-[#6B7280] mt-1">{c.location}</span>
              </button>
            ))}
          </div>
        </section>

        <section aria-labelledby="model-heading">
          <p className={eyebrow}>Step 2</p>
          <h2 id="model-heading" className="text-[24px] font-bold tracking-tight text-[#111827] mb-4">Choose an apartment</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {community.models.map((m) => (
              <button key={m.id} type="button" aria-pressed={m.id === model.id} data-testid={`model-${m.id}`}
                      className={choice(m.id === model.id)} onClick={() => pickModel(m)}>
                <span className="block text-lg font-medium text-[#111827]">{m.name}</span>
                <span className="block text-sm text-[#6B7280] mt-1">{bedroomLabel(m)} · {formatSquareFeet(m.squareFeet)}</span>
              </button>
            ))}
          </div>
        </section>

        <section aria-labelledby="configure-heading" className="grid grid-cols-1 lg:grid-cols-12 gap-10">
          <div className="lg:col-span-7">
            <p className={eyebrow}>Step 3</p>
            <h2 id="configure-heading" className="text-[24px] font-bold tracking-tight text-[#111827]">{model.name}</h2>
            <p className="text-[#6B7280] mb-4" data-testid="model-facts">
              {bedroomLabel(model)} · {formatSquareFeet(model.squareFeet)}
              {community.dataStatus === "demo" && " · demo figures"}
            </p>
            <FloorPlanView model={model} selected={selected} />
            {community.source && (
              <p className="text-xs text-[#6B7280] mt-2">
                Floor plan and square footage: {community.source.publisher}, retrieved {community.source.retrievedAt}.
              </p>
            )}
          </div>
          <div className="lg:col-span-5">
            <h3 className="text-xl text-[#111827] mb-4 lg:mt-12">Choose CAOSCare features</h3>
            <RoomFeatureConfigurator features={features} selected={selected} onToggle={toggle} onShow={panel.open} />
          </div>
        </section>

        <ExperiencePanel model={model} features={features} selected={selected} />
      </main>
      <CapabilityPanel capability={panel.capability} open={panel.isOpen} onClose={panel.close}
        onCloseAutoFocus={panel.onCloseAutoFocus} />
    </PublicPage>
  );
}
