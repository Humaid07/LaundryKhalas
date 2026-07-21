"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation } from "@tanstack/react-query";
import { ArrowRight, Send } from "lucide-react";
import { api, ApiError } from "@/lib/api-client";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { JsonViewer } from "@/components/ui/json-viewer";
import { MARKET_CODES, OUT_OF_SCOPE_HINTS, SAMPLE_MESSAGES } from "@/lib/constants";

export default function MockWhatsAppConsolePage() {
  const [marketCode, setMarketCode] = useState<string>(MARKET_CODES[0]);
  const [phoneNumber, setPhoneNumber] = useState("+971501234567");
  const [customerName, setCustomerName] = useState("");
  const [message, setMessage] = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      api.mockWhatsappInbound({
        market_code: marketCode,
        phone_number: phoneNumber,
        customer_name: customerName || undefined,
        message,
      }),
  });

  const matchedHint = OUT_OF_SCOPE_HINTS.find((h) => h.match.test(message));

  return (
    <div>
      <PageHeader
        title="WhatsApp Console"
        description="Send an inbound WhatsApp message into the system. No live WhatsApp message is sent."
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <h2 className="text-sm font-semibold text-ink">New Inbound Message</h2>
          </CardHeader>
          <CardBody className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Market">
                <select
                  value={marketCode}
                  onChange={(e) => setMarketCode(e.target.value)}
                  className="w-full rounded-lg border border-border-strong bg-white px-3 py-2 text-sm text-ink"
                >
                  {MARKET_CODES.map((code) => (
                    <option key={code} value={code}>
                      {code}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Phone number">
                <input
                  value={phoneNumber}
                  onChange={(e) => setPhoneNumber(e.target.value)}
                  placeholder="+971501234567"
                  className="w-full rounded-lg border border-border-strong bg-white px-3 py-2 text-sm text-ink"
                />
              </Field>
            </div>

            <Field label="Customer name (optional)">
              <input
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
                placeholder="Jane Doe"
                className="w-full rounded-lg border border-border-strong bg-white px-3 py-2 text-sm text-ink"
              />
            </Field>

            <Field label="Message">
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                rows={4}
                placeholder="I need laundry pickup tomorrow"
                className="w-full resize-none rounded-lg border border-border-strong bg-white px-3 py-2 text-sm text-ink"
              />
            </Field>

            <div className="flex flex-wrap gap-1.5">
              {SAMPLE_MESSAGES.map((sample) => (
                <button
                  key={sample}
                  onClick={() => setMessage(sample)}
                  className="rounded-full border border-border-strong bg-white px-2.5 py-1 text-xs text-ink-muted hover:bg-neutral-soft"
                >
                  {sample}
                </button>
              ))}
            </div>

            {matchedHint && (
              <p className="rounded-lg bg-warning-soft px-3 py-2 text-xs text-warning-text">
                {matchedHint.hint}
              </p>
            )}

            <Button
              variant="primary"
              onClick={() => mutation.mutate()}
              disabled={!phoneNumber.trim() || !message.trim() || mutation.isPending}
            >
              <Send className="h-3.5 w-3.5" />
              Send Inbound Message
            </Button>

            {mutation.isError && (
              <p className="text-sm text-danger">
                {mutation.error instanceof ApiError ? mutation.error.detail : "Something went wrong."}
              </p>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <h2 className="text-sm font-semibold text-ink">Result</h2>
          </CardHeader>
          <CardBody>
            {!mutation.data && !mutation.isPending && (
              <p className="text-sm text-ink-muted">
                Submit a message to see the created conversation, message, and customer id here.
              </p>
            )}
            {mutation.isPending && <p className="text-sm text-ink-muted">Sending…</p>}
            {mutation.data && (
              <div className="space-y-3">
                <Link
                  href={`/admin/conversations/${mutation.data.conversation_id}`}
                  className="flex items-center justify-between rounded-lg border border-success/30 bg-success-soft px-4 py-3 text-sm font-medium text-success-text hover:bg-success-soft/70"
                >
                  Open conversation
                  <ArrowRight className="h-4 w-4" />
                </Link>
                <JsonViewer data={mutation.data} label="Raw API response" defaultOpen />
              </div>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-ink-muted">{label}</span>
      {children}
    </label>
  );
}
