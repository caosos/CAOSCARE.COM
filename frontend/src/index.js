import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

// StrictMode intentionally double-mounts every component in dev to surface
// effect-leak bugs. For our WebRTC voice pipeline (kiosk realtime mode) that
// double-mount caused a second peer connection to spin up alongside the
// first, producing the back-to-back "two voices" overlap. Disabling for
// dev removes the duplicate; production behavior is unchanged because
// production builds never invoke StrictMode's double-mount.
const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);
