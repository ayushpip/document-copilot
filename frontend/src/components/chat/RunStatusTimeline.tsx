import { Check, Loader2 } from 'lucide-react'

import { cn } from '@/lib/utils'

type RunStatusTimelineProps = {
  stages: string[]
  activeStage: string | null
}

export function RunStatusTimeline({ stages, activeStage }: RunStatusTimelineProps) {
  const activeIndex = Math.max(
    0,
    stages.findIndex((stage) => stage === activeStage),
  )

  return (
    <div className="rounded-md border border-border bg-muted/30 px-3 py-3">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Assistant run</p>
      <ol className="mt-3 space-y-2">
        {stages.map((stage, index) => {
          const isDone = index < activeIndex
          const isActive = index === activeIndex

          return (
            <li key={stage} className="flex items-center gap-2 text-sm">
              <span
                className={cn(
                  'flex size-5 items-center justify-center rounded-full border text-[10px]',
                  isDone && 'border-foreground bg-foreground text-background',
                  isActive && 'border-foreground bg-background text-foreground',
                  !isDone && !isActive && 'border-border bg-background text-muted-foreground',
                )}
              >
                {isDone ? <Check className="size-3" /> : null}
                {isActive ? <Loader2 className="size-3 animate-spin" /> : null}
              </span>
              <span className={cn(isActive ? 'text-foreground' : 'text-muted-foreground')}>{stage}</span>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
