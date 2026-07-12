import { AlertCircle } from 'lucide-react'

type ChatErrorBannerProps = {
  message: string
}

export function ChatErrorBanner({ message }: ChatErrorBannerProps) {
  return (
    <div className="border-t border-border bg-background px-4 py-3">
      <div className="mx-auto flex max-w-4xl items-start gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
        <AlertCircle className="mt-0.5 size-4 shrink-0" />
        <p>{message}</p>
      </div>
    </div>
  )
}
