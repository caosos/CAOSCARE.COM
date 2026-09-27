import React from "react";
import { EXPERIENCE_VIDEOS } from "../../lib/experienceVideos";

// Public "resident experience" video library. The first entry is featured;
// any further entries render as a grid below it, so the library can grow by
// adding data (lib/experienceVideos.js), not by redesigning this section.
// Playback is always user-started with the video's own audio: no autoplay,
// and preload="none" so the page never downloads video nobody asked for.

function ExperienceVideo({ video, featured }) {
  const titleId = `xp-${video.id}-title`;
  const summaryId = `xp-${video.id}-summary`;
  return (
    <figure className="m-0" data-testid={`experience-video-${video.id}`}>
      <div
        className={`overflow-hidden bg-caos-forest ${
          featured ? "rounded-[32px] shadow-2xl" : "rounded-2xl shadow-lg"
        }`}
      >
        <video
          className="block w-full aspect-video bg-caos-forest"
          controls
          preload="none"
          playsInline
          poster={video.poster}
          aria-labelledby={titleId}
          aria-describedby={summaryId}
        >
          <source src={video.src} type="video/mp4" />
          Your browser can't play this video.{" "}
          <a href={video.src}>Download the video</a>.
        </video>
      </div>
      <figcaption className="mt-4">
        <p className="text-xs font-bold uppercase tracking-[0.22em] text-caos-mute">
          Video {video.number} · {video.duration} · {video.kind}
        </p>
        <p id={titleId} className="font-display text-xl font-medium text-caos-forest mt-1">
          {video.title}
        </p>
        <p id={summaryId} className="text-caos-mute mt-1 leading-relaxed">
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
      className="px-6 md:px-12 py-20 border-t border-caos-line"
      aria-labelledby="experience-library-heading"
      data-testid="experience-video-library"
    >
      <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-12 gap-12 items-center">
        <div className="md:col-span-4">
          <p className="text-xs font-bold uppercase tracking-[0.22em] text-caos-mute mb-4">
            Video library
          </p>
          <h2
            id="experience-library-heading"
            className="font-display text-3xl md:text-5xl font-light tracking-tight text-caos-forest"
          >
            See CAOSCare in everyday life.
          </h2>
          <p className="text-lg text-caos-ink mt-6 leading-relaxed">
            Aria isn't a device the resident has to operate. The room is Aria.
          </p>
          <ul className="mt-6 space-y-3 text-caos-ink">
            <li className="flex gap-3"><span className="w-1 bg-caos-terracotta" />No complicated interface</li>
            <li className="flex gap-3"><span className="w-1 bg-caos-terracotta" />No new device to learn</li>
            <li className="flex gap-3"><span className="w-1 bg-caos-terracotta" />Just talk naturally to the room</li>
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
