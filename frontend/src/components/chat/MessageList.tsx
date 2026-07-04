import type { ChatMessageRole } from '@/lib/chat-api'

export type DisplayMessage = {
  id: string
  role: ChatMessageRole
  content: string
}

type MessageListProps = {
  messages: DisplayMessage[]
  isStreaming: boolean
}

export function MessageList({ messages, isStreaming }: MessageListProps) {
  if (messages.length === 0) {
    return (
      <div className="grid min-h-full place-items-center px-6 py-12 text-center">
        <div>
          <h1 className="text-2xl font-semibold tracking-normal text-foreground">Start a filing question</h1>
          <p className="mt-3 max-w-md text-sm leading-6 text-muted-foreground">
            This phase streams a stubbed reply and saves history. Retrieval and citations come next.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4 px-6 py-6">
      {messages.map((message) => (
        <article
          key={message.id}
          className={`max-w-3xl rounded-lg border px-4 py-3 text-sm leading-6 ${
            message.role === 'user'
              ? 'ml-auto border-primary/20 bg-primary text-primary-foreground'
              : 'border-border bg-card text-card-foreground'
          }`}
        >
          <p className="mb-1 text-xs font-medium uppercase text-current opacity-70">{message.role}</p>
          <p className="whitespace-pre-wrap">{message.content}</p>
        </article>
      ))}
      {isStreaming ? <p className="px-1 text-sm text-muted-foreground">Assistant is streaming...</p> : null}
    </div>
  )
}
