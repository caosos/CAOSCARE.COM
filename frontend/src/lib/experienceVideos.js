// CAOSCare resident-experience video library — the single list the public
// site renders. To add a video: put the MP4 (+ a poster JPEG) in
// frontend/public/media/, append one entry here. No page changes needed.
//
// Keep descriptions to what the video shows and what CAOSCare actually
// does; the films are illustrative scenes, not product claims.
// Written brand is always "CAOSCare" (spoken "KAY-oss Care").

export const EXPERIENCE_VIDEOS = [
  {
    id: "resident-experience-01",
    number: "001",
    // Owner 2026-10-16 (#162 c6209371153): "Aria — your personal helper" framing. These are
    // generated scenes with visibly artificial motion in places: never product proof.
    title: "Aria — your personal helper",
    summary:
      "A room that hears you and can help you: speak naturally, with no screen to find and no device to learn.",
    src: "/media/caoscare-resident-experience-01.mp4",
    poster: "/media/caoscare-resident-experience-01-poster.jpg",
    duration: "0:30",
    kind: "Illustrative film · generated scenes, not product footage",
  },
];
