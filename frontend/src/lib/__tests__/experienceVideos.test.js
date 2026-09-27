import fs from "fs";
import path from "path";
import { EXPERIENCE_VIDEOS } from "../experienceVideos";

const PUBLIC = path.join(__dirname, "..", "..", "..", "public");

describe("resident-experience video library", () => {
  test("has at least one video, with unique ids and numbers", () => {
    expect(EXPERIENCE_VIDEOS.length).toBeGreaterThan(0);
    expect(new Set(EXPERIENCE_VIDEOS.map((v) => v.id)).size).toBe(EXPERIENCE_VIDEOS.length);
    expect(new Set(EXPERIENCE_VIDEOS.map((v) => v.number)).size).toBe(EXPERIENCE_VIDEOS.length);
  });

  test.each(EXPERIENCE_VIDEOS.map((v) => [v.id, v]))("%s: every field set and assets exist", (_id, v) => {
    for (const key of ["id", "number", "title", "summary", "src", "poster", "duration", "kind"]) {
      expect(v[key]).toBeTruthy();
    }
    for (const asset of [v.src, v.poster, v.captions].filter(Boolean)) {
      expect(asset.startsWith("/media/")).toBe(true);
      expect(fs.existsSync(path.join(PUBLIC, asset))).toBe(true);
    }
    expect(v.src.endsWith(".mp4")).toBe(true);
  });
});
