// The CAOSCare house-and-heart mark: the app sidebar and the public site draw this one SVG.
export default function CaosCareMark({ className = "h-[54px] w-[54px]" }) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden="true">
      <path d="M8 30 L32 9 L56 30" fill="none" stroke="#1E4E8C" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M15 27 V53 H49 V27" fill="none" stroke="#1E4E8C" strokeWidth="5" strokeLinejoin="round" />
      <path d="M32 50 C22 43 20 37 24 33 C27 30 31 31 32 34 C33 31 37 30 40 33 C44 37 42 43 32 50 Z" fill="#E4589A" />
      <path d="M20 44 C25 47 29 49 32 50" fill="none" stroke="#2F80ED" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}
