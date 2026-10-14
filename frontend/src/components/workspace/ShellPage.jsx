import WorkspaceShell from "./WorkspaceShell";

// An existing page shown inside the shared shell unchanged; its own sticky
// brand/back header is hidden (the shell's sidebar, header and breadcrumbs
// replace it — index.css .ws-embedded).
export default function ShellPage({ crumbs, activeSection, children }) {
  return (
    <WorkspaceShell crumbs={crumbs} activeSection={activeSection}>
      <div className="ws-embedded -mx-5 mt-2 sm:-mx-9">{children}</div>
    </WorkspaceShell>
  );
}
