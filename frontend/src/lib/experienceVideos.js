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
    title: "The room is Aria",
    summary:
      "A resident's day, spoken naturally to the room — no screen to find, no device to learn.",
    src: "/media/caoscare-resident-experience-01.mp4",
    poster: "/media/caoscare-resident-experience-01-poster.jpg",
    duration: "0:30",
    kind: "Illustrative scenes",
  },
];
