import { redirect } from "next/navigation";

// Facilities landing → the Overview metrics page (the canonical first view).
// The Directory lives at /facilities/directory.
export default function Page() {
  redirect("/facilities/overview");
}
