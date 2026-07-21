"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { Check, ChevronDown, X } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * FilterSelect — the dashboard's custom dropdown/select.
 *
 * A lightweight, dependency-free listbox that replaces the native <select> in
 * both the global FilterBar and the LocalFilterBar. Premium rounded styling,
 * rose accent for the active/selected state, full dark-mode support, and
 * keyboard + screen-reader accessible (button = combobox trigger, ul = listbox).
 *
 * Behaviour: click/Enter/Space/ArrowDown opens; click-outside & Escape close;
 * Arrow/Home/End move the highlight; Enter/Space or click commits and closes;
 * chevron rotates while open; menu flips to right-align near the viewport edge.
 * An empty value ("") means "no filter" and maps to the leading "All …" row.
 */

export type FilterSelectProps = {
  /** Accessible name + placeholder shown when nothing is selected. */
  label: string;
  value: string;
  options: readonly string[];
  onChange: (value: string) => void;
  /** Overrides `label` as the trigger placeholder text. */
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  /** Optional leading icon in the trigger. */
  icon?: ReactNode;
  /** Show an inline clear (×) button in the trigger when a value is set. */
  clearable?: boolean;
};

export function FilterSelect({
  label,
  value,
  options,
  onChange,
  placeholder,
  disabled = false,
  className,
  icon,
  clearable = false,
}: FilterSelectProps) {
  const [open, setOpen] = useState(false);
  const [align, setAlign] = useState<"left" | "right">("left");
  const [activeIndex, setActiveIndex] = useState(-1); // -1 = the "All …" row
  const rootRef = useRef<HTMLDivElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const listboxId = useId();

  const active = Boolean(value);
  const display = value || placeholder || label;
  const showClear = clearable && active && !disabled;

  // Close on outside click.
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  // Keep the keyboard-highlighted option scrolled into view.
  useEffect(() => {
    if (!open || activeIndex < 0 || !listRef.current) return;
    const el = listRef.current.querySelector(`[data-idx="${activeIndex}"]`) as HTMLElement | null;
    el?.scrollIntoView({ block: "nearest" });
  }, [activeIndex, open]);

  const openMenu = () => {
    if (disabled) return;
    const rect = btnRef.current?.getBoundingClientRect();
    if (rect) setAlign(rect.left > window.innerWidth * 0.6 ? "right" : "left");
    setActiveIndex(value ? options.indexOf(value) : -1);
    setOpen(true);
  };

  const commit = (v: string) => {
    onChange(v);
    setOpen(false);
    btnRef.current?.focus();
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (disabled) return;
    if (!open) {
      if (e.key === "ArrowDown" || e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        openMenu();
      }
      return;
    }
    switch (e.key) {
      case "Escape":
        e.preventDefault();
        setOpen(false);
        btnRef.current?.focus();
        break;
      case "ArrowDown":
        e.preventDefault();
        setActiveIndex((i) => Math.min(i + 1, options.length - 1));
        break;
      case "ArrowUp":
        e.preventDefault();
        setActiveIndex((i) => Math.max(i - 1, -1));
        break;
      case "Home":
        e.preventDefault();
        setActiveIndex(0);
        break;
      case "End":
        e.preventDefault();
        setActiveIndex(options.length - 1);
        break;
      case "Enter":
      case " ":
        e.preventDefault();
        commit(activeIndex < 0 ? "" : options[activeIndex]);
        break;
    }
  };

  return (
    <div ref={rootRef} className={cn("relative inline-block", className)}>
      <button
        ref={btnRef}
        type="button"
        disabled={disabled}
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listboxId : undefined}
        aria-label={label}
        onClick={() => (open ? setOpen(false) : openMenu())}
        onKeyDown={onKeyDown}
        className={cn(
          "inline-flex h-9 items-center gap-2 rounded-full border text-xs font-medium transition-all duration-200 ease-out-quint focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose/40",
          showClear ? "pl-3.5 pr-8" : "pl-3.5 pr-2.5",
          disabled && "cursor-not-allowed opacity-50",
          !disabled &&
            (active
              ? "border-rose/40 bg-rose/10 text-rose hover:bg-rose/[0.14]"
              : open
                ? "border-rose/30 bg-surface text-ink shadow-card"
                : "border-border bg-surface text-ink hover:border-border-strong hover:bg-surface-2"),
        )}
      >
        {icon && <span className={cn("shrink-0", active ? "text-rose" : "text-ink-faint")}>{icon}</span>}
        <span className={cn("max-w-[10rem] truncate", !active && "text-ink")}>{display}</span>
        {!showClear && (
          <ChevronDown
            className={cn(
              "h-3.5 w-3.5 shrink-0 transition-transform duration-200 ease-out-quint",
              open && "rotate-180",
              active ? "text-rose/70" : "text-ink-faint",
            )}
          />
        )}
      </button>

      {showClear && (
        <button
          type="button"
          aria-label={`Clear ${label} filter`}
          onClick={() => commit("")}
          className="absolute right-1.5 top-1/2 grid h-5 w-5 -translate-y-1/2 place-items-center rounded-full text-rose/70 transition-colors hover:bg-rose/15 hover:text-rose focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose/40"
        >
          <X className="h-3 w-3" />
        </button>
      )}

      {open && (
        <ul
          ref={listRef}
          id={listboxId}
          role="listbox"
          aria-label={label}
          tabIndex={-1}
          className={cn(
            "lk-menu-in absolute z-50 mt-2 max-h-72 min-w-[11rem] max-w-[min(16rem,calc(100vw-2rem))] overflow-auto rounded-2xl border border-border bg-surface-raised p-1.5 shadow-pop",
            align === "right" ? "right-0" : "left-0",
          )}
        >
          <Option
            dataIdx={-1}
            selected={!active}
            highlighted={activeIndex === -1}
            muted
            onSelect={() => commit("")}
            onHover={() => setActiveIndex(-1)}
          >
            All {label.toLowerCase()}
          </Option>
          {options.map((o, i) => (
            <Option
              key={o}
              dataIdx={i}
              selected={o === value}
              highlighted={activeIndex === i}
              onSelect={() => commit(o)}
              onHover={() => setActiveIndex(i)}
            >
              {o}
            </Option>
          ))}
        </ul>
      )}
    </div>
  );
}

function Option({
  children,
  dataIdx,
  selected,
  highlighted,
  muted = false,
  onSelect,
  onHover,
}: {
  children: ReactNode;
  dataIdx: number;
  selected: boolean;
  highlighted: boolean;
  muted?: boolean;
  onSelect: () => void;
  onHover: () => void;
}) {
  return (
    <li
      role="option"
      aria-selected={selected}
      data-idx={dataIdx}
      onMouseEnter={onHover}
      onClick={onSelect}
      className={cn(
        "flex cursor-pointer items-center justify-between gap-2 rounded-lg px-3 py-2 text-xs font-medium transition-colors",
        selected
          ? "bg-rose/12 text-rose"
          : highlighted
            ? "bg-rose/[0.07] text-ink"
            : muted
              ? "text-ink-muted hover:bg-surface-2"
              : "text-ink hover:bg-surface-2",
      )}
    >
      <span className="truncate">{children}</span>
      {selected && <Check className="h-3.5 w-3.5 shrink-0 text-rose" />}
    </li>
  );
}
