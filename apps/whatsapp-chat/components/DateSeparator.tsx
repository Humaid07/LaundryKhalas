export function DateSeparator({ label }: { label: string }) {
  return (
    <div className="my-2 flex justify-center">
      <span className="rounded-md bg-white/80 px-3 py-1 text-[11px] font-medium text-wa-muted shadow-sm">
        {label}
      </span>
    </div>
  );
}
