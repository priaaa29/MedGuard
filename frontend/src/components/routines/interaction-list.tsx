import { AlertOctagon, AlertTriangle, Info } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { SEVERITY_LABELS, SEVERITY_ORDER, SOURCE_LABELS } from "@/lib/format";
import type { InteractionFinding, Severity } from "@/lib/types";

const SEVERITY_STYLE: Record<Severity, { icon: typeof Info; badge: "destructive" | "warning" | "secondary" }> = {
  High: { icon: AlertOctagon, badge: "destructive" },
  Medium: { icon: AlertTriangle, badge: "warning" },
  Low: { icon: Info, badge: "secondary" },
};

export function InteractionList({ findings }: { findings: InteractionFinding[] }) {
  if (findings.length === 0) {
    return (
      <p className="text-muted-foreground">
        No known food or drug interactions for these medicines in MedGuard&apos;s data. That doesn&apos;t rule
        everything out, so ask your pharmacist if you&apos;re unsure about a food or drink.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      {SEVERITY_ORDER.map((severity) => {
        const group = findings.filter((finding) => finding.severity === severity);
        if (group.length === 0) return null;
        const { icon: Icon, badge } = SEVERITY_STYLE[severity];
        return (
          <section key={severity} aria-labelledby={`severity-${severity}`}>
            <h3 id={`severity-${severity}`} className="mb-3 flex items-center gap-2 font-medium">
              <Badge variant={badge}>
                <Icon aria-hidden />
                {SEVERITY_LABELS[severity]}
              </Badge>
              <span className="text-sm text-muted-foreground tabular-nums">{group.length}</span>
            </h3>
            <ul className="space-y-3">
              {group.map((finding, index) => (
                <li
                  // Index included: routines saved before backend de-duplication can repeat a pair.
                  key={`${finding.medicine}-${finding.interacts_with}-${index}`}
                  className="rounded-lg border border-border bg-card px-4 py-3"
                >
                  <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                    <p className="font-medium">
                      {finding.medicine} + {finding.interacts_with}
                    </p>
                    <span className="text-xs text-muted-foreground">{SOURCE_LABELS[finding.source]}</span>
                  </div>
                  <p className="mt-1 text-sm">{finding.effect}</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    <span className="font-medium text-foreground">What to do:</span> {finding.recommendation}
                  </p>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
