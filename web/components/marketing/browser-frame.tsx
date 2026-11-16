import { cn } from "@/lib/utils";

export function BrowserFrame({
  children,
  label = "OpenOncology · demo case",
  tone = "light",
  className,
}: {
  children: React.ReactNode;
  label?: string;
  tone?: "light" | "dark";
  className?: string;
}) {
  const dark = tone === "dark";
  return (
    <div
      className={cn(
        "overflow-hidden rounded-xl border",
        dark ? "border-white/10 bg-[#15111F] shadow-[0_40px_120px_-30px_rgb(123_108_240/0.45)]" : "border-oo-line bg-oo-surface shadow-[0_50px_100px_-40px_rgb(27_22_38/0.35)]",
        className
      )}
    >
      <div className={cn("flex h-9 items-center gap-3 border-b px-3.5", dark ? "border-white/10" : "border-oo-line")}>
        <span className="flex gap-1.5" aria-hidden="true">
          {[0, 1, 2].map((i) => (
            <span key={i} className={cn("h-2.5 w-2.5 rounded-full", dark ? "bg-white/15" : "bg-oo-line")} />
          ))}
        </span>
        <span
          className={cn(
            "mx-auto rounded-md px-3 py-0.5 font-mono text-[11px]",
            dark ? "bg-white/5 text-white/50" : "bg-oo-paper text-oo-ink-3"
          )}
        >
          {label}
        </span>
        <span className="w-[42px]" aria-hidden="true" />
      </div>
      {children}
    </div>
  );
}
