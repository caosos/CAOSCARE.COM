import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { FileText, Search, Sparkles } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import WorkspaceShell from "../components/workspace/WorkspaceShell";
import MarkdownView from "../components/workspace/MarkdownView";

// Settings > Documents: the curated project documents (GET /documents),
// grouped by category with description and revision. Owner-only documents
// are listed only for the owner; the server enforces it.
export default function DocumentsPage() {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [q, setQ] = useState("");
  const [doc, setDoc] = useState(null);
  const [sp, setSp] = useSearchParams();
  const openId = sp.get("doc");

  useEffect(() => {
    api.get("/documents").then(({ data: d }) => setData(d))
      .catch((e) => setError(e?.response?.data?.detail || "Could not load documents"));
  }, []);
  useEffect(() => {
    if (!openId) { setDoc(null); return; }
    setDoc({ loading: true });
    api.get(`/documents/${encodeURIComponent(openId)}`).then(({ data: d }) => setDoc(d))
      .catch((e) => setDoc({ error: e?.response?.data?.detail || "Could not open the document" }));
  }, [openId]);

  const groups = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (data?.categories || []).map((c) => ({
      ...c,
      docs: data.documents.filter((d) => d.category === c.id
        && (!needle || `${d.title} ${d.description}`.toLowerCase().includes(needle))),
    })).filter((c) => c.docs.length);
  }, [data, q]);

  const crumbs = doc && openId
    ? [{ label: "Settings" }, { label: "Documents", to: "/documents" }, { label: doc.title || "Document" }]
    : [{ label: "Settings" }, { label: "Documents" }];

  return (
    <WorkspaceShell crumbs={crumbs}>
      {openId ? (
        <article className="mx-auto mt-4 max-w-4xl rounded-2xl border border-[#E5E7EB] bg-white p-6 sm:p-10" data-testid="document-view">
          <Link to="/documents" className="text-[14px] text-[#2F80ED] hover:underline">← All documents</Link>
          {doc?.loading && <p className="mt-4 text-[#6B7280]">Loading…</p>}
          {doc?.error && <p className="mt-4 text-[#B42318]">{doc.error}</p>}
          {doc?.text && (
            <>
              <p className="mt-3 text-[13px] text-[#6B7280]">{doc.path} · revision {doc.revision?.commit || "not recorded"}
                {doc.revision?.date ? ` · ${doc.revision.date}` : ""}</p>
              <div className="mt-4"><MarkdownView text={doc.text} /></div>
            </>
          )}
        </article>
      ) : (
        <>
          <div className="mt-1 flex flex-col items-start justify-between gap-4 sm:flex-row">
            <div>
              <h1 className="text-[28px] font-bold leading-tight tracking-tight sm:text-[36px]">Documents</h1>
              <p className="mt-1 text-[17px] text-[#4B5563] sm:text-[20px]">Blueprints, specifications, procedures and reports</p>
            </div>
            {user?.role === "owner" && (
              <Link to="/admin/blueprint" data-testid="documents-blueprint"
                    className="flex items-center gap-2 rounded-lg border border-[#E5E7EB] bg-white px-4 py-2.5 text-[15px] font-medium hover:bg-[#F9FAFB]">
                <Sparkles className="h-4 w-4 text-[#2F80ED]" /> Interactive blueprint
              </Link>
            )}
          </div>
          <label className="mt-6 flex items-center gap-2 rounded-lg border border-[#E5E7EB] bg-white px-3 py-2.5">
            <Search className="h-4 w-4 text-[#9CA3AF]" />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search documents" aria-label="Search documents"
                   className="w-full bg-transparent text-[15px] outline-none" />
          </label>
          {error && <p className="mt-4 text-[#B42318]">{error}</p>}
          {!data && !error && <p className="mt-4 text-[#6B7280]">Loading…</p>}
          <div className="mt-6 space-y-8" data-testid="documents-list">
            {groups.map((g) => (
              <section key={g.id}>
                <h2 className="text-[18px] font-semibold">{g.label}</h2>
                <ul className="mt-3 grid gap-3 md:grid-cols-2">
                  {g.docs.map((d) => (
                    <li key={d.id}>
                      <button type="button" onClick={() => setSp({ doc: d.id })} data-testid={`doc-${d.id}`}
                              className="flex w-full items-start gap-3 rounded-xl border border-[#E5E7EB] bg-white p-4 text-left hover:border-[#2F80ED]">
                        <FileText className="mt-0.5 h-5 w-5 shrink-0 text-[#2F80ED]" />
                        <span className="min-w-0">
                          <span className="block font-semibold text-[#111827]">{d.title}
                            {d.owner_only && <span className="ml-2 rounded bg-[#EEF2FF] px-1.5 py-0.5 text-[11px] font-medium text-[#3730A3]">Owner</span>}
                          </span>
                          <span className="mt-0.5 block text-[14px] text-[#4B5563]">{d.description}</span>
                          <span className="mt-1 block text-[12px] text-[#9CA3AF]">
                            {d.revision?.commit ? `Revision ${d.revision.commit} · ${d.revision.date}` : "Revision not recorded"}
                          </span>
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        </>
      )}
    </WorkspaceShell>
  );
}
