// Minimal, safe Markdown display for project documents: headings, lists,
// code blocks, tables (as preformatted text), quotes and paragraphs. Builds
// React elements only (no HTML injection); inline **bold** and `code`.
function Inline({ text }) {
  const parts = String(text).split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((p, i) => {
    if (p.startsWith("**") && p.endsWith("**")) return <strong key={i}>{p.slice(2, -2)}</strong>;
    if (p.startsWith("`") && p.endsWith("`")) return <code key={i} className="rounded bg-[#F3F4F6] px-1 text-[0.92em]">{p.slice(1, -1)}</code>;
    return p;
  });
}

export default function MarkdownView({ text }) {
  const lines = String(text || "").split("\n");
  const out = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.startsWith("```")) {
      const block = [];
      i += 1;
      while (i < lines.length && !lines[i].startsWith("```")) { block.push(lines[i]); i += 1; }
      out.push(<pre key={out.length} className="overflow-x-auto rounded-lg bg-[#F6F8FA] p-3 text-[13px]">{block.join("\n")}</pre>);
      i += 1;
      continue;
    }
    const h = line.match(/^(#{1,4})\s+(.*)/);
    if (h) {
      const size = ["text-[26px]", "text-[21px]", "text-[18px]", "text-[16px]"][h[1].length - 1];
      out.push(<div key={out.length} role="heading" aria-level={h[1].length} className={`mt-5 font-semibold ${size}`}><Inline text={h[2]} /></div>);
      i += 1;
      continue;
    }
    if (/^\s*([-*]|\d+\.)\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*([-*]|\d+\.)\s+/, "")); i += 1;
      }
      out.push(<ul key={out.length} className="ml-5 list-disc space-y-1">{items.map((t, j) => <li key={j}><Inline text={t} /></li>)}</ul>);
      continue;
    }
    if (line.startsWith("|")) {
      const rows = [];
      while (i < lines.length && lines[i].startsWith("|")) { rows.push(lines[i]); i += 1; }
      out.push(<pre key={out.length} className="overflow-x-auto rounded-lg border border-[#E5E7EB] p-3 text-[13px]">{rows.join("\n")}</pre>);
      continue;
    }
    if (line.startsWith(">")) {
      out.push(<blockquote key={out.length} className="border-l-4 border-[#D1D5DB] pl-3 text-[#4B5563]"><Inline text={line.replace(/^>\s?/, "")} /></blockquote>);
      i += 1;
      continue;
    }
    if (line.trim()) {
      const para = [];
      while (i < lines.length && lines[i].trim() && !/^(#{1,4}\s|```|\||>|\s*([-*]|\d+\.)\s)/.test(lines[i])) { para.push(lines[i]); i += 1; }
      out.push(<p key={out.length}><Inline text={para.join(" ")} /></p>);
      continue;
    }
    i += 1;
  }
  return <div className="space-y-3 text-[15px] leading-relaxed text-[#1F2937]">{out}</div>;
}
