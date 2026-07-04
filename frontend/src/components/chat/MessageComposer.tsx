import { useState, type FormEvent } from 'react'
import { SendHorizontal } from 'lucide-react'

import { Button } from '@/components/ui/button'

type MessageComposerProps = {
  disabled: boolean
  onSubmit: (content: string) => Promise<void>
}

export function MessageComposer({ disabled, onSubmit }: MessageComposerProps) {
  const [content, setContent] = useState('')

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmed = content.trim()

    if (!trimmed || disabled) {
      return
    }

    setContent('')
    await onSubmit(trimmed)
  }

  return (
    <form className="border-t border-border bg-background p-4" onSubmit={handleSubmit}>
      <div className="mx-auto flex max-w-4xl items-end gap-2">
        <textarea
          className="min-h-20 flex-1 resize-none rounded-md border border-input bg-background px-3 py-2 text-sm leading-6 text-foreground outline-none transition focus:border-ring focus:ring-2 focus:ring-ring/30"
          value={content}
          placeholder="Ask about filings..."
          disabled={disabled}
          onChange={(event) => setContent(event.target.value)}
        />
        <Button className="h-10" type="submit" disabled={disabled || content.trim() === ''}>
          <SendHorizontal />
          Send
        </Button>
      </div>
    </form>
  )
}
