import { FacilityDetailPage } from "@/components/dashboard/facilities/FacilityDetailPage";

export default async function Page({ params }: { params: Promise<{ facilityId: string }> }) {
  const { facilityId } = await params;
  return <FacilityDetailPage facilityId={facilityId} />;
}
