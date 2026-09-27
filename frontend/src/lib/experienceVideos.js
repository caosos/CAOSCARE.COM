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
    title: "Good morning, Aria",
    summary:
      "A resident greets Aria and hears the morning information in one room.",
    src: "/media/caoscare-resident-greeting-01.mp4",
    poster: "/media/caoscare-resident-greeting-01-poster.jpg",
    captions: "/media/caoscare-resident-greeting-01.vtt",
    duration: "0:09",
    kind: "Illustrative scene",
  },
];
