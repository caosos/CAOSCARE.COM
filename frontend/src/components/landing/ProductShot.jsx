// A real CAOSCare screen in a plain window frame, always with a caption that
// says where the picture came from (sample or simulated data, never residents).
export default function ProductShot({ src, alt, caption, label, className = "", eager = false }) {
  return (
    <figure className={`m-0 ${className}`}>
      <div className="overflow-hidden rounded-xl border border-[#E5E7EB] bg-white shadow-[0_12px_40px_-12px_rgba(17,24,39,0.25)]">
        <div className="flex items-center gap-1.5 border-b border-[#E5E7EB] bg-[#F9FAFB] px-3 py-2" aria-hidden="true">
          <span className="h-2.5 w-2.5 rounded-full bg-[#E5E7EB]" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#E5E7EB]" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#E5E7EB]" />
          {label && <span className="ml-2 truncate text-[12px] text-[#6B7280]">{label}</span>}
        </div>
        <img src={src} alt={alt} loading={eager ? "eager" : "lazy"} className="block h-auto w-full" />
      </div>
      {caption && <figcaption className="mt-2 text-[13px] leading-snug text-[#6B7280]">{caption}</figcaption>}
    </figure>
  );
}
