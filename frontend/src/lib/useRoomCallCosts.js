import { useEffect, useState } from "react";
import { api } from "./api";

export default function useRoomCallCosts(refreshMs = 15000) {
  const [rooms, setRooms] = useState(null);
  useEffect(() => {
    let stopped = false;
    const load = () => api.get("/paid-api/call-costs/latest-by-room", { timeout: 5000 })
      .then(({ data }) => { if (!stopped) setRooms(data?.rooms || {}); })
      .catch(() => { if (!stopped) setRooms((current) => current || {}); });
    load();
    const timer = setInterval(load, refreshMs);
    return () => { stopped = true; clearInterval(timer); };
  }, [refreshMs]);
  return rooms;
}
