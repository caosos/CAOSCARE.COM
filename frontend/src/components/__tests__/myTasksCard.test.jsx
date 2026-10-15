import React, { act } from "react";
import { createRoot } from "react-dom/client";
import MyTasksCard from "../MyTasksCard";

const mockGet = jest.fn();
jest.mock("../../lib/api", () => ({ api: { get: (...a) => mockGet(...a), post: jest.fn() } }));
jest.mock("@/lib/utils", () => ({ cn: (...a) => a.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("../ui/dialog", () => ({ Dialog: () => null, DialogContent: () => null, DialogFooter: () => null,
                                   DialogHeader: () => null, DialogTitle: () => null }));
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

test("loads the signed-in worker's tasks and offers only the permitted next action", async () => {
  mockGet.mockResolvedValue({ data: [
    { task_id: "a", title: "Night room check", status: "pending", priority: "normal", resident_name: "SIM Resident 003",
      room: "SIM-003", category: "nursing", created_at: "2026-10-15T03:41:00Z" },
    { task_id: "b", title: "Help to the bathroom", status: "in_progress", priority: "high", resident_name: "SIM Resident 004",
      room: "SIM-004", category: "nursing", created_at: "2026-10-15T03:45:00Z", started_at: "2026-10-15T04:40:00Z",
      resident_words: "I need help to the bathroom, please." },
  ] });
  const el = document.createElement("div");
  const root = createRoot(el);
  await act(async () => root.render(<MyTasksCard />));
  await act(async () => { await Promise.resolve(); });
  // the same request the workspace has always used for "my tasks"
  expect(mockGet).toHaveBeenCalledWith("/tasks", { params: { mine_only: true } });
  const text = el.textContent;
  for (const s of ["Night room check", "SIM Resident 003", "Room SIM-003", "Resident said", "2 open"]) expect(text).toContain(s);
  expect(el.querySelector("[data-testid=start-task-a]")).not.toBeNull();
  expect(el.querySelector("[data-testid=complete-task-a]")).toBeNull();
  expect(el.querySelector("[data-testid=complete-task-b]")).not.toBeNull();
  expect(el.querySelector("[data-testid=start-task-b]")).toBeNull();
  await act(async () => root.unmount());
});
