"use client";

import { useQuery } from "@tanstack/react-query";
import { facilityApi } from "./api-client";

/** Shared unread-count query — the header bell and bottom-nav badge read the
 *  same cache key so they always agree. Polls every 60s. Fails soft to 0. */
export function useUnreadCount() {
  const q = useQuery({
    queryKey: ["notifications", "unread-count"],
    queryFn: async () => {
      try {
        const res = await facilityApi.unreadCount();
        return res?.count ?? 0;
      } catch {
        return 0;
      }
    },
    refetchInterval: 60_000,
  });
  return q.data ?? 0;
}
