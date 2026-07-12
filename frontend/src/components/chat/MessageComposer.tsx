import { useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { SendHorizontal } from 'lucide-react'

import { Button } from '@/components/ui/button'

type MessageComposerProps = {
  disabled: boolean
  onSubmit: (content: string) => Promise<boolean>
}

export function MessageComposer({ disabled, onSubmit }: MessageComposerProps) {
  const [content, setContent] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

  function resizeTextarea() {
    const textarea = textareaRef.current
    if (!textarea) {
      return
    }
    textarea.style.height = 'auto'
    textarea.style.height = `${Math.min(textarea.scrollHeight, 220)}px`
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmed = content.trim()

    if (!trimmed || disabled) {
      return
    }

    setContent('')
    requestAnimationFrame(resizeTextarea)
    const wasAccepted = await onSubmit(trimmed)
    if (!wasAccepted) {
      setContent(trimmed)
      requestAnimationFrame(resizeTextarea)
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== 'Enter' || event.shiftKey) {
      return
    }
    event.preventDefault()
    event.currentTarget.form?.requestSubmit()
  }

  return (
    <form className="border-t border-border bg-background/95 p-4" onSubmit={handleSubmit}>
      <div className="mx-auto flex max-w-4xl items-end gap-2 rounded-lg border border-border bg-card p-2 shadow-sm">
        <textarea
          ref={textareaRef}
          className="max-h-[220px] min-h-12 flex-1 resize-none rounded-md border-0 bg-transparent px-2 py-2 text-sm leading-6 text-foreground outline-none placeholder:text-muted-foreground"
          value={content}
          placeholder="Ask about filings..."
          disabled={disabled}
          rows={1}
          onChange={(event) => {
            setContent(event.target.value)
            requestAnimationFrame(resizeTextarea)
          }}
          onKeyDown={handleKeyDown}
        />
        <Button className="h-9" type="submit" disabled={disabled || content.trim() === ''} aria-label="Send message">
          <SendHorizontal />
          <span className="hidden sm:inline">Send</span>
        </Button>
      </div>
      <p className="mx-auto mt-2 max-w-4xl px-1 text-xs text-muted-foreground">Enter to send. Shift+Enter for a new line.</p>
    </form>
  )
}
