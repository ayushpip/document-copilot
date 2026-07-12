import { FileSearch } from 'lucide-react'

import { Button } from '@/components/ui/button'

type ChatEmptyStateProps = {
  disabled: boolean
  onSelectPrompt: (prompt: string) => void
}

const STARTER_PROMPTS = [
  "Compare Microsoft's Intelligent Cloud revenue growth, operating income growth, and operating margin trends across fiscal years 2022-2025.",
  "How did Apple's revenue mix change across iPhone, Services, Mac, iPad, and Wearables from fiscal 2021 to fiscal 2025?",
  "Compare NVIDIA's Data Center and Gaming revenue growth across the available filings. Which segment drove the larger change in NVIDIA's revenue mix?",
]

export function ChatEmptyState({ disabled, onSelectPrompt }: ChatEmptyStateProps) {
  return (
    <div className="grid min-h-full place-items-center px-5 py-10 text-center">
      <div className="max-w-2xl">
        <div className="mx-auto mb-5 flex size-11 items-center justify-center rounded-lg border border-border bg-background">
          <FileSearch className="size-5" />
        </div>
        <h1 className="!m-0 !text-2xl font-semibold tracking-normal text-foreground">Ask a filing question</h1>
        <p className="mx-auto mt-3 max-w-lg text-sm leading-6 text-muted-foreground">
          Start with a company, filing year, segment, risk factor, or metric. Answers stay tied to retrieved source passages.
        </p>
        <div className="mt-7 grid gap-2 text-left">
          {STARTER_PROMPTS.map((prompt) => (
            <Button
              key={prompt}
              type="button"
              variant="outline"
              className="h-auto justify-start whitespace-normal rounded-md px-3 py-2 text-left text-sm leading-5"
              disabled={disabled}
              onClick={() => onSelectPrompt(prompt)}
            >
              {prompt}
            </Button>
          ))}
        </div>
      </div>
    </div>
  )
}
