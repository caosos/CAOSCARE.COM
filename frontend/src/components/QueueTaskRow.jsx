import { useEffect, useState } from "react";
import { CalendarClock, Car, Check, ChevronRight, Eye, Hand, History, NotebookPen, Play, XCircle } from "lucide-react";
import { api } from "../lib/api";
import { Button } from "./ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import RequestTimeline from "./RequestTimeline";
import { ReviewBadge } from "./ExceptionReview";
import { inspectionText } from "./InspectionControls";
import { itemsLine } from "../lib/requestItems";
import { detailsLine } from "../lib/appointmentDetails";
import { rideLine, canRequestRide } from "../lib/rideLink";
import { ageLabel, canClaim, isOverdue } from "../lib/maintenance";

const PRIO = { urgent: "bg-[#FEE2E2] text-[#B42318]", high: "bg-[#FFEDD5] text-[#C2410C]",
               normal: "bg-[#F3F4F6] text-[#374151]", low: "bg-[#F3F4F6] text-[#6B7280]" };
const STATUS = { pending: "bg-[#FEF3C7] text-[#92400E]", in_progress: "bg-[#DBEAFE] text-[#1E40AF]",
                 completed: "bg-[#DCFCE7] text-[#166534]", skipped: "bg-[#F3F4F6] text-[#6B7280]" };
const clock = (iso) => (iso ? new Date(iso).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : null);
const minutesBetween = (a, b) => (a && b ? Math.max(0, Math.round((new Date(b) - new Date(a)) / 60000)) : null);
const open = (t) => t.status !== "completed" && t.status !== "skipped";
// A simulator ticket's own event id carries its simulated day
// (simulator:event:day-NNN:...); real time is shown alongside, never instead.
export const simDayOf = (t) => {
  const m = (t.conversation_session_id || "").match(/^simulator:event:day-(\d+):/);
  return m ? Number(m[1]) + 1 : null;
};

function Pill({ tone, children, testid }) {
  return <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase ${tone}`} data-testid={testid}>{children}</span>;
}

// One department request as a compact row; expanding it shows the full
// request, the action toolbar (every action the old card had, same ids),
// assignment, work duration, outcome, and the timeline with its receipts.
export default function QueueTaskRow({ t, ride, ctx }) {
  const [expanded, setExpanded] = useState(false);
  const [detail, setDetail] = useState(null);
  useEffect(() => {
    if (!expanded) return;
    let live = true;
    api.get(`/tasks/${t.task_id}/detail`).then(({ data }) => live && setDetail(data)).catch(() => live && setDetail({ failed: true }));
    return () => { live = false; };
  }, [expanded, t.task_id, t.status, t.notes]);

  const overdue = isOverdue(t);
  const simDay = simDayOf(t);
  const requested = [t.requested_for_time_label, t.requested_for_date].filter(Boolean).join(" · ")
    || `${simDay ? `Sim day ${simDay} · ` : ""}${clock(t.created_at)}`;
  const worked = minutesBetween(t.started_at, t.completed_at);
  const { user, act, claim, start, openComplete, openNote, openPlan, requestRide, openCancel, openHistory,
          review, isAdmin, canNote, canPlan, showAssign, roster, assignTo, isOlder } = ctx;
  const tool = "h-8 px-2.5 text-[13px]";
  return (
    <div className="bg-white" data-testid={`wo-${t.task_id}`}>
      {/* Sizes by its own width (flex-wrap), so it reads well in a narrow
          column (Work as) as well as full width. */}
      <button type="button" onClick={() => setExpanded((v) => !v)} aria-expanded={expanded}
              data-testid={`wo-row-${t.task_id}`}
              className="flex w-full flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 text-left hover:bg-caos-bone">
        <ChevronRight className={`h-4 w-4 shrink-0 text-caos-mute transition-transform ${expanded ? "rotate-90" : ""}`} />
        <span className="min-w-[12rem] flex-1">
          <span className="block truncate text-[14px] font-semibold text-caos-ink">{t.title}</span>
          <span className="block truncate text-[12px] text-caos-mute">
            {[t.resident_name, t.room ? `Room ${t.room}` : null].filter(Boolean).join(" · ") || "No resident"}
            {t.simulated ? " · SIM" : ""}
            {isOlder(t) && <> · <span title={t.currency?.reason || ""} data-testid={`wo-older-${t.task_id}`}>needs review</span></>}
          </span>
        </span>
        <span className="flex flex-wrap items-center gap-x-3 gap-y-1 pl-7 sm:pl-0">
          <Pill tone={PRIO[t.priority] || PRIO.normal}>{t.priority}</Pill>
          <Pill tone={STATUS[t.status] || STATUS.pending}>{t.status.replace("_", " ")}</Pill>
          <span className="max-w-[11rem] truncate text-[13px] text-caos-ink">{t.assigned_name || <span className="text-caos-mute">Unassigned</span>}</span>
          <span className="text-[12px] text-caos-mute">{requested}</span>
          <span className={`text-[12px] ${overdue ? "font-semibold text-caos-terracotta" : "text-caos-mute"}`}>
            {ageLabel(t.created_at)}{overdue ? " · overdue" : ""}
          </span>
        </span>
      </button>

      {expanded && (
        <div className="space-y-3 border-t border-caos-line bg-caos-bone/40 px-4 py-3 text-[14px]" data-testid={`wo-expanded-${t.task_id}`}>
          <div className="space-y-1">
            {t.resident_words ? <div>Resident said: "{t.resident_words}"</div>
              : t.description && t.description !== t.title && <div>{t.description}</div>}
            {itemsLine(t.items) && <div className="font-semibold" data-testid={`wo-items-${t.task_id}`}>{itemsLine(t.items)}</div>}
            <ReviewBadge t={t} />
            {inspectionText(t) && <div className="font-semibold text-caos-amber" data-testid={`wo-returned-${t.task_id}`}>{inspectionText(t)}</div>}
            {(t.requested_for_date || t.requested_for_time_label) && (
              <div data-testid={`wo-planned-${t.task_id}`}>Planned: {[t.requested_for_time_label, t.requested_for_date].filter(Boolean).join(" · ")}</div>
            )}
            {(t.provider_name || t.discipline || t.location) && <div data-testid={`wo-details-${t.task_id}`}>{detailsLine(t)}</div>}
            {rideLine(ride) && <div data-testid={`wo-ride-status-${t.task_id}`}>{rideLine(ride)}</div>}
            <div className="text-[13px] text-caos-mute">
              {[t.acknowledged_at ? `Seen by ${t.acknowledged_by_name || "staff"} ${clock(t.acknowledged_at)}` : "Not yet acknowledged",
                t.started_at ? `started ${clock(t.started_at)}` : null,
                t.completed_at ? `finished ${clock(t.completed_at)}` : null,
                worked != null ? `work time ${worked} min` : null,
                t.re_request_count > 0 ? `asked ${t.re_request_count + 1}x` : null].filter(Boolean).join(" · ")}
            </div>
            {t.notes && !(inspectionText(t) && t.notes.startsWith("Returned after inspection:")) && <div>Outcome / note: {t.notes}</div>}
          </div>

          <div className="flex flex-wrap items-center gap-1.5" role="toolbar" aria-label="Request actions">
            {!t.acknowledged_at && open(t) && (
              <Button size="sm" variant="outline" className={tool} onClick={() => act(t.task_id, "acknowledge")} data-testid={`wo-ack-${t.task_id}`}><Eye className="mr-1 h-4 w-4" />Acknowledge</Button>)}
            {canClaim(t, user) && (
              <Button size="sm" variant="outline" className={tool} onClick={() => claim(t.task_id)} data-testid={`wo-claim-${t.task_id}`}><Hand className="mr-1 h-4 w-4" />Claim</Button>)}
            {t.status === "pending" && (
              <Button size="sm" className={`${tool} bg-caos-forest text-white hover:bg-caos-forest-hover`} onClick={() => start(t.task_id)} data-testid={`wo-start-${t.task_id}`}><Play className="mr-1 h-4 w-4" />Start</Button>)}
            {t.status === "in_progress" && (
              <Button size="sm" variant="outline" className={tool} onClick={() => openComplete(t.task_id)} data-testid={`wo-complete-${t.task_id}`}><Check className="mr-1 h-4 w-4" />Complete</Button>)}
            {canNote(t) && open(t) && (
              <Button size="sm" variant="ghost" className={tool} onClick={() => openNote(t.task_id)} data-testid={`wo-note-${t.task_id}`}><NotebookPen className="mr-1 h-4 w-4" />Note</Button>)}
            {canPlan(t) && open(t) && (
              <Button size="sm" variant="ghost" className={tool} onClick={() => openPlan(t.task_id)} data-testid={`wo-plan-${t.task_id}`}><CalendarClock className="mr-1 h-4 w-4" />Plan</Button>)}
            {canPlan(t) && canRequestRide(t, ride) && (
              <Button size="sm" variant="ghost" className={tool} onClick={() => requestRide(t.task_id)} data-testid={`wo-ride-${t.task_id}`}><Car className="mr-1 h-4 w-4" />Ride</Button>)}
            {canPlan(t) && open(t) && (
              <Button size="sm" variant="ghost" className={`${tool} text-caos-terracotta`} onClick={() => openCancel(t.task_id)} data-testid={`wo-cancel-${t.task_id}`}><XCircle className="mr-1 h-4 w-4" />Cancel</Button>)}
            {review.buttons(t, { canAct: canPlan(t), isAdmin })}
            <Button size="sm" variant="ghost" className={tool} onClick={() => openHistory(t.task_id)} data-testid={`wo-history-${t.task_id}`}><History className="mr-1 h-4 w-4" />History</Button>
            {showAssign && open(t) && (
              <Select value={t.assigned_to || "__none"} onValueChange={(v) => assignTo(t.task_id, v === "__none" ? "" : v)}>
                <SelectTrigger className="h-8 w-48 text-xs" data-testid={`wo-assign-${t.task_id}`}><SelectValue placeholder="Assign to…" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none">Unassigned</SelectItem>
                  {roster.map((u) => <SelectItem key={u.user_id} value={u.user_id}>{u.name}</SelectItem>)}
                </SelectContent>
              </Select>
            )}
          </div>

          <div className="rounded-lg border border-caos-line bg-white p-3" data-testid={`wo-timeline-${t.task_id}`}>
            {!detail && <span className="text-caos-mute">Loading timeline and receipts…</span>}
            {detail?.failed && <span className="text-caos-terracotta">Could not load the timeline.</span>}
            {detail?.task && <RequestTimeline task={detail.task} receipts={detail.receipts} />}
          </div>
        </div>
      )}
    </div>
  );
}
