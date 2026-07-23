import {
  drivers, pickupQueue, deliveryQueue, driverIssues,
  type Driver, type PickupJob, type DeliveryJob, type DriverIssue,
} from "@/lib/dashboard/operations-data";

/** URL-safe slug for a driver name, e.g. "Ahmed Khan" → "ahmed-khan". */
export function driverSlug(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

export interface DriverWithTasks {
  driver: Driver;
  pickups: PickupJob[];
  deliveries: DeliveryJob[];
  issues: DriverIssue[];
}

/** Resolve a driver + all of their assigned tasks for the detail page. */
export function getDriver(slug: string): DriverWithTasks | undefined {
  const driver = drivers.find((d) => driverSlug(d.name) === slug);
  if (!driver) return undefined;
  return {
    driver,
    pickups: pickupQueue.filter((p) => p.driver === driver.name),
    deliveries: deliveryQueue.filter((d) => d.driver === driver.name),
    issues: driverIssues.filter((i) => i.driver === driver.name),
  };
}
