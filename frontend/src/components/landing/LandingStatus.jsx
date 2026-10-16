import { ALL_CAPABILITIES } from "../../lib/capabilities";
import { STATUS_META, STATUS_ORDER, statusOf } from "../../lib/capabilities/status";
import { STATUS_STYLE } from "../capabilities/StatusPill";

// "What works today": grouped straight from the one public status registry
// (lib/capabilities/status.js), so this page can never claim more than the others.
const GROUPS = STATUS_ORDER.map((key) => ({ key, tone: STATUS_STYLE[key].panel, dot: STATUS_STYLE[key].dot }));

export default function LandingStatus({ onOpen }) {
  const byStatus = (key) => ALL_CAPABILITIES.filter((c) => statusOf(c.id) === key);
  return (
    <section className="px-4 py-16 sm:px-6 lg:px-8" aria-labelledby="status-title" data-testid="landing-status">
      <div className="mx-auto max-w-7xl">
        <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-[#2F80ED]">Honest status</p>
        <h2 id="status-title" className="mt-2 text-[28px] font-bold leading-tight tracking-tight text-[#111827] sm:text-[36px]">
          What works today, and what is still being built
        </h2>
        <p className="mt-3 max-w-3xl text-[17px] leading-relaxed text-[#4B5563]">
          CAOSCare is in pilot: proven in our test apartment and exercised on a simulated 75-resident community.
          It is not yet running in a customer community. Open any item for what it does and its stated limits.
        </p>
        <div className="mt-8 grid grid-cols-1 gap-4 lg:auto-cols-fr lg:grid-flow-col">
          {GROUPS.map((g) => {
            const items = byStatus(g.key);
            if (!items.length) return null;
            return (
              <div key={g.key} data-status={g.key} className={`rounded-xl border p-5 ${g.tone}`}>
                <h3 className="flex items-center gap-2 text-[17px] font-semibold text-[#111827]">
                  <span className={`h-2.5 w-2.5 rounded-full ${g.dot}`} aria-hidden="true" />
                  {STATUS_META[g.key].label} <span className="font-normal text-[#6B7280]">· {items.length}</span>
                </h3>
                <p className="mt-1 text-[14px] text-[#4B5563]">{STATUS_META[g.key].meaning}</p>
                <ul className="mt-4 flex flex-wrap gap-2">
                  {items.map((c) => (
                    <li key={c.id}>
                      <button type="button" onClick={() => onOpen(c.id)} data-testid={`status-${c.id}`}
                              className="rounded-full border border-[#D1D5DB] bg-white px-3 py-1.5 text-[14px] text-[#111827] hover:border-[#111827]">
                        {c.name}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
