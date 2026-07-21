"use client";

import { useState } from "react";
import { ImagePlus, Sparkles, Send, CalendarClock, Wand2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Panel, PanelHeader, StatusBadge } from "./ui/primitives";
import { Button } from "./ui/Button";

const OUTPUT_TYPES = ["Social image", "Carousel", "Reel / video concept", "HeyGen-style video", "Gamma-style carousel"];
const PLATFORMS = ["Instagram", "Facebook", "TikTok", "LinkedIn"];
const INTEGRATIONS = [
  { name: "HeyGen", label: "Video avatars" },
  { name: "Gamma", label: "Carousels" },
  { name: "Meta / Instagram", label: "Publishing" },
  { name: "Composio", label: "Connectors" },
  { name: "Apollo", label: "Outreach" },
];

export function CreativeStudio() {
  const [outputType, setOutputType] = useState(OUTPUT_TYPES[0]);
  const [platform, setPlatform] = useState(PLATFORMS[0]);
  const [prompt, setPrompt] = useState("Fresh Eid linen — book a WhatsApp pickup in Dubai Marina");
  const [generated, setGenerated] = useState(false);

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {/* Composer */}
      <Panel>
        <PanelHeader title="AI Creative Studio" subtitle="Draft creative — nothing posts without approval" />

        <label className="mb-1.5 block text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Prompt</label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={3}
          className="w-full resize-none rounded-xl border border-border bg-surface-2 px-3 py-2.5 text-sm text-ink placeholder:text-ink-faint focus:border-rose focus-visible:outline-none"
          placeholder="Describe the post you want to create…"
        />

        <button
          type="button"
          className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-border bg-surface-2 py-4 text-xs text-ink-muted transition-colors hover:border-rose/40 hover:text-ink"
        >
          <ImagePlus className="h-4 w-4" /> Upload reference image (optional)
        </button>

        <div className="mt-4">
          <p className="mb-1.5 text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Output type</p>
          <div className="flex flex-wrap gap-1.5">
            {OUTPUT_TYPES.map((t) => (
              <Chip key={t} active={outputType === t} onClick={() => setOutputType(t)}>{t}</Chip>
            ))}
          </div>
        </div>

        <div className="mt-4">
          <p className="mb-1.5 text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Platform</p>
          <div className="flex flex-wrap gap-1.5">
            {PLATFORMS.map((p) => (
              <Chip key={p} active={platform === p} onClick={() => setPlatform(p)}>{p}</Chip>
            ))}
          </div>
        </div>

        <Button variant="primary" className="mt-5 w-full justify-center" onClick={() => setGenerated(true)}>
          <Wand2 className="h-4 w-4" /> Generate preview
        </Button>

        <div className="mt-4 flex flex-wrap gap-1.5">
          {INTEGRATIONS.map((i) => (
            <span key={i.name} className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface-2 px-2 py-1 text-xxs text-ink-muted">
              <span className="h-1.5 w-1.5 rounded-full bg-ink-faint" /> {i.name}
              <span className="text-ink-faint">· {i.label}</span>
            </span>
          ))}
        </div>
        <p className="mt-2 text-xxs text-ink-faint">Connect an integration to publish approved creatives directly.</p>
      </Panel>

      {/* Preview */}
      <Panel className="flex flex-col">
        <PanelHeader title="Preview" subtitle={`${outputType} · ${platform}`} action={<StatusBadge tone="warning" dot={false}>Draft</StatusBadge>} />
        <div className="flex flex-1 flex-col">
          <div className="relative flex min-h-[220px] flex-1 items-center justify-center overflow-hidden rounded-xl border border-border bg-gradient-to-br from-rose/10 via-surface-2 to-[rgb(var(--c-plum)/0.08)]">
            {generated ? (
              <div className="p-6 text-center">
                <span className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-rose text-rose-contrast shadow-rose-glow">
                  <Sparkles className="h-6 w-6" />
                </span>
                <p className="font-display text-lg font-semibold text-ink">Fresh for Eid ✨</p>
                <p className="mt-1 text-sm text-ink-muted">{prompt}</p>
                <p className="mt-3 text-xxs uppercase tracking-eyebrow text-ink-faint">Generated creative · {platform}</p>
              </div>
            ) : (
              <div className="flex flex-col items-center text-ink-faint">
                <Sparkles className="mb-2 h-6 w-6" />
                <p className="text-xs">Your generated preview will appear here</p>
              </div>
            )}
          </div>
          <div className="mt-3 rounded-xl border border-border bg-surface-2 p-3">
            <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Caption</p>
            <p className="mt-1 text-sm text-ink">
              {generated ? "Eid-ready wardrobe starts here ✨ Book your pickup on WhatsApp. #LaundryKhalas #Dubai" : "—"}
            </p>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button variant="primary" size="sm" disabled={!generated}><Send className="h-3.5 w-3.5" /> Send for approval</Button>
            <Button variant="secondary" size="sm" disabled={!generated}><CalendarClock className="h-3.5 w-3.5" /> Schedule after approval</Button>
          </div>
        </div>
      </Panel>
    </div>
  );
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-colors",
        active ? "border-rose bg-rose/10 text-rose" : "border-border bg-surface text-ink-muted hover:border-border-strong hover:text-ink",
      )}
    >
      {children}
    </button>
  );
}
