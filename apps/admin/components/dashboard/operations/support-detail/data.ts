import { tickets } from "@/lib/dashboard/mock-data";
import type { Ticket } from "@/lib/dashboard/types";

/** Look up a single support ticket by id for its detail page. */
export function getTicket(id: string): Ticket | undefined {
  return tickets.find((t) => t.id === id);
}
