// Shared between TasksTab.jsx and TaskTemplatesBoard.jsx (split 2026-09-21
// to keep both files within the file-size guideline - see AGENTS.md
// "Change discipline"). One source of truth for the task category/shift
// vocabulary rather than two independently-maintained copies.
export const CATEGORIES = ["laundry", "meds", "meal", "rounds", "bathing", "housekeeping", "activity", "transport", "check_in", "paperwork", "other"];
export const SHIFTS = ["day", "evening", "night", "any"];
