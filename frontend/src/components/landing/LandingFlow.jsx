import ProductShot from "./ProductShot";

// Resident → staff → receipt: the three things a visitor should understand in 30 seconds,
// each shown with a real CAOSCare screen.
const STEPS = [
  {
    n: "1", who: "The resident",
    title: "Asks Aria, or presses help",
    body: "Residents talk to Aria from their chair or bed (\"Hey Aria\"), press a familiar help pendant, or use one simple room screen. No tablet to learn.",
    shot: { src: "/media/product/room-screen.jpg", alt: "CAOSCare room screen with Call for help and I just want to talk buttons",
            label: "Room screen", caption: "Real room screen · public demo room, sample resident" },
  },
  {
    n: "2", who: "The staff",
    title: "See it in the right department",
    body: "The request lands in that department's queue in the resident's own words. Staff see who is on duty, who owns it and how long it has waited.",
    shot: { src: "/media/product/department.jpg", alt: "CAOSCare department view listing staff on duty and waiting work",
            label: "Department view", caption: "Real workspace · simulated community, synthetic staff" },
  },
  {
    n: "3", who: "The record",
    title: "Every step leaves a receipt",
    body: "Requested, claimed, started, finished: each step records who acted, when and under what authority. The resident and Aria hear the true status, never a guess.",
    shot: { src: "/media/product/ticket-receipts.jpg", alt: "CAOSCare ticket detail with request, start and finish times and its receipts",
            label: "Ticket detail", caption: "Real ticket view · simulated community, synthetic data" },
  },
];

export default function LandingFlow() {
  return (
    <section className="border-t border-[#E5E7EB] bg-[#F9FAFB] px-4 py-16 sm:px-6 lg:px-8" aria-labelledby="flow-title">
      <div className="mx-auto max-w-7xl">
        <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-[#2F80ED]">How it works</p>
        <h2 id="flow-title" className="mt-2 max-w-3xl text-[28px] font-bold leading-tight tracking-tight text-[#111827] sm:text-[36px]">
          One request, from the room to the right person, with proof.
        </h2>
        <ol className="mt-10 grid grid-cols-1 gap-10 lg:grid-cols-3 lg:gap-8">
          {STEPS.map((s) => (
            <li key={s.n} className="flex min-w-0 flex-col">
              <div className="flex items-baseline gap-3">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#111827] text-[15px] font-bold text-white">{s.n}</span>
                <span className="text-[13px] font-semibold uppercase tracking-[0.12em] text-[#6B7280]">{s.who}</span>
              </div>
              <h3 className="mt-3 text-[21px] font-semibold text-[#111827]">{s.title}</h3>
              <p className="mt-2 text-[16px] leading-relaxed text-[#4B5563]">{s.body}</p>
              <ProductShot className="mt-5" {...s.shot} />
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
