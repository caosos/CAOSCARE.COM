import {
  humanizeAction, receiptStatusTone, eventStatusTone, fmtDuration,
  receiptLink, summarizeMetadata, distinct,
} from "../activityLog";

describe("humanizeAction", () => {
  test("splits dots/underscores and capitalises", () => {
    expect(humanizeAction("task_created")).toBe("Task created");
    expect(humanizeAction("admin_aria.tool_call")).toBe("Admin aria tool call");
    expect(humanizeAction("")).toBe("—");
    expect(humanizeAction(null)).toBe("—");
  });
});

describe("receiptStatusTone", () => {
  test("maps the fixed ReceiptStatus set", () => {
    expect(receiptStatusTone("completed")).toBe("ok");
    expect(receiptStatusTone("failed")).toBe("bad");
    expect(receiptStatusTone("in_progress")).toBe("info");
    expect(receiptStatusTone("created")).toBe("muted");
    expect(receiptStatusTone("weird")).toBe("muted");
  });
});

describe("eventStatusTone", () => {
  test("keyword-buckets free-text event status", () => {
    expect(eventStatusTone("command_verified")).toBe("ok");
    expect(eventStatusTone("ok")).toBe("ok");
    expect(eventStatusTone("error")).toBe("bad");
    expect(eventStatusTone("command_failed")).toBe("bad");
    expect(eventStatusTone("command_sent")).toBe("info");
    expect(eventStatusTone("")).toBe("muted");
  });
});

describe("fmtDuration", () => {
  test("ms / s / m thresholds", () => {
    expect(fmtDuration(0)).toBe("");
    expect(fmtDuration(-5)).toBe("");
    expect(fmtDuration(250)).toBe("250ms");
    expect(fmtDuration(1500)).toBe("1.5s");
    expect(fmtDuration(120000)).toBe("2m");
    expect(fmtDuration("nope")).toBe("");
  });
});

describe("receiptLink", () => {
  test("routes by related_object_type; task splits on source", () => {
    expect(receiptLink({ related_object_type: "alert" })).toEqual({ type: "route", value: "/staff" });
    expect(receiptLink({ related_object_type: "device_command" })).toEqual({ type: "tab", value: "devices" });
    expect(receiptLink({ related_object_type: "task", source: "staff" })).toEqual({ type: "tab", value: "tasks" });
    expect(receiptLink({ related_object_type: "task", source: "aria_voice" })).toEqual({ type: "tab", value: "requests" });
    expect(receiptLink({ related_object_type: "task" })).toEqual({ type: "tab", value: "tasks" });
    expect(receiptLink({ related_object_type: "mystery" })).toBe(null);
    expect(receiptLink(null)).toBe(null);
  });
});

describe("summarizeMetadata", () => {
  test("prefers a known text field, else counts keys", () => {
    expect(summarizeMetadata({ message: "hello there" })).toBe("hello there");
    expect(summarizeMetadata({ utterance: "x".repeat(200) }).endsWith("…")).toBe(true);
    expect(summarizeMetadata({ a: 1, b: 2, c: 3 })).toBe("3 fields: a, b, c");
    expect(summarizeMetadata({})).toBe("");
    expect(summarizeMetadata(null)).toBe("");
  });
});

describe("distinct", () => {
  test("unique non-blank values, sorted", () => {
    expect(distinct([{ s: "b" }, { s: "a" }, { s: "b" }, { s: "" }, { s: null }], "s")).toEqual(["a", "b"]);
    expect(distinct(null, "s")).toEqual([]);
  });
});
