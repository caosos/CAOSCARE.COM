import React from "react";
import { EXPERIENCE_VIDEOS } from "../../lib/experienceVideos";

// Public "resident experience" video library. The first entry is featured;
// any further entries render as a grid below it, so the library can grow by
// adding data (lib/experienceVideos.js), not by redesigning this section.
// Playback is always user-started with the video's own audio: no autoplay,
// and preload="none" so the page never downloads video nobody asked for.

export function ExperienceVideo({ video, featured }) {
  const titleId = `xp-${video.id}-title`;
  const summaryId = `xp-${video.id}-summary`;
  return (
    <figure className="m-0" data-testid={`experience-video-${video.id}`}>
      <div
        className={`overflow-hidden bg-[#111827] ${
          featured ? "rounded-xl shadow-[0_12px_40px_-12px_rgba(17,24,39,0.35)]" : "rounded-xl shadow-md"
        }`}
      >
        <video
          className="block w-full aspect-video bg-[#111827]"
          controls
          preload="none"
          playsInline
          poster={video.poster}
          aria-labelledby={titleId}
          aria-describedby={summaryId}
        >
          <source src={video.src} type="video/mp4" />
          {video.captions && <track kind="captions" src={video.captions} srcLang="en" label="English" default />}
          Your browser can't play this video.{" "}
          <a href={video.src}>Download the video</a>.
        </video>
      </div>
      <figcaption className="mt-4">
        <p className="text-[12px] font-semibold uppercase tracking-[0.1em] text-[#6B7280]">
          Video {video.number} · {video.duration} · {video.kind}
        </p>
        <p id={titleId} className="mt-1 text-[19px] font-semibold text-[#111827]">
          {video.title}
        </p>
        <p id={summaryId} className="mt-1 text-[15px] leading-relaxed text-[#4B5563]">
          {video.summary}
        </p>
      </figcaption>
    </figure>
  );
}

export default function ExperienceVideoLibrary() {
  const [featured, ...more] = EXPERIENCE_VIDEOS;
  if (!featured) return null;
  return (
    <section
      className="border-t border-[#E5E7EB] px-4 py-16 sm:px-6 lg:px-8"
      aria-labelledby="experience-library-heading"
      data-testid="experience-video-library"
    >
      <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-12 gap-12 items-center">
        <div className="md:col-span-4">
          <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-[#2F80ED]">
            Video library
          </p>
          <h2
            id="experience-library-heading"
            className="mt-2 text-[28px] font-bold leading-tight tracking-tight text-[#111827] sm:text-[36px]"
          >
            See CAOSCare in everyday life.
          </h2>
          <p className="mt-4 text-[17px] leading-relaxed text-[#4B5563]">
            Aria isn't a device the resident has to operate. The room is Aria.
          </p>
          <ul className="mt-6 space-y-3 text-[16px] text-[#111827]">
            <li className="flex gap-3"><span className="w-1 rounded bg-[#2F80ED]" />No complicated interface</li>
            <li className="flex gap-3"><span className="w-1 rounded bg-[#2F80ED]" />No new device to learn</li>
            <li className="flex gap-3"><span className="w-1 rounded bg-[#2F80ED]" />Just talk naturally to the room</li>
          </ul>
        </div>
        <div className="md:col-span-8">
          <ExperienceVideo video={featured} featured />
        </div>
      </div>
      {more.length > 0 && (
        <div className="max-w-7xl mx-auto mt-16 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-8">
          {more.map((v) => (
            <ExperienceVideo key={v.id} video={v} />
          ))}
        </div>
      )}
    </section>
  );
}
