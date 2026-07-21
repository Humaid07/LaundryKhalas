import type { Tone } from "./types";

export const orderStatusTone: Record<string, Tone> = {
  New: "info",
  "Pickup Scheduled": "info",
  "Driver Assigned": "plum",
  "Picked Up": "plum",
  "In Cleaning": "warning",
  "Ready for Delivery": "rose",
  "Out for Delivery": "rose",
  Delivered: "success",
  Cancelled: "neutral",
  "Concern Raised": "danger",
};

export const paymentTone: Record<string, Tone> = {
  Paid: "success",
  Pending: "warning",
  Refunded: "neutral",
  Failed: "danger",
};

export const agentStatusTone: Record<string, Tone> = {
  Active: "success",
  Scheduled: "info",
  "Needs Review": "warning",
  "Awaiting Approval": "rose",
  Paused: "neutral",
  Failed: "danger",
};

export const priorityTone: Record<string, Tone> = {
  Urgent: "danger",
  High: "warning",
  Medium: "info",
  Low: "neutral",
};

export const ticketStatusTone: Record<string, Tone> = {
  Open: "warning",
  "In Progress": "info",
  Waiting: "neutral",
  Resolved: "success",
};

export const convStatusTone: Record<string, Tone> = {
  "AI handling": "success",
  "Awaiting reply": "warning",
  "Human takeover": "rose",
  Resolved: "neutral",
};

export const riskTone: Record<string, Tone> = {
  Low: "success",
  Medium: "warning",
  High: "danger",
};

export const connectionTone: Record<string, Tone> = {
  Connected: "success",
  "Not connected": "neutral",
  "Coming soon": "info",
  "Needs approval": "warning",
};

export const marketingStatusTone: Record<string, Tone> = {
  "Awaiting Approval": "rose",
  Scheduled: "info",
  "Changes Requested": "warning",
  Draft: "neutral",
  Active: "success",
  Paused: "neutral",
};

export const reportStatusTone: Record<string, Tone> = {
  Ready: "success",
  Generating: "warning",
  Scheduled: "info",
};
