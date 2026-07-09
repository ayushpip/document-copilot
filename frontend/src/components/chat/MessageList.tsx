import { FileText } from 'lucide-react'

import type { ChatCitation, ChatMessageRole } from '@/lib/chat-api'

export type DisplayMessage = {
  id: string
  role: ChatMessageRole
  content: string
  citations?: ChatCitation[]
}

type MessageListProps = {
  messages: DisplayMessage[]
  isStreaming: boolean
  runStage: string | null
  selectedCitation: ChatCitation | null
  onSelectCitation: (citation: ChatCitation) => void
}

function messageBody(content: string, role: ChatMessageRole) {
  if (role !== 'assistant') {
    return content
  }
  return content.split('\n\nCitations:\n')[0]
}

function CitationChips({
  citations,
  selectedCitation,
  onSelectCitation,
}: {
  citations: ChatCitation[]
  selectedCitation: ChatCitation | null
  onSelectCitation: (citation: ChatCitation) => void
}) {
  if (citations.length === 0) {
    return null
  }

  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {citations.map((citation) => {
        const isSelected = selectedCitation?.chunk_id === citation.chunk_id
        const label = `${citation.company} ${citation.filing_type} ${citation.filing_year}`
        const detail = citation.section ? citation.section : `chunk ${citation.chunk_index}`

        return (
          <button
            key={citation.chunk_id}
            type="button"
            className={`inline-flex max-w-full items-center gap-1.5 rounded-md border px-2 py-1 text-xs transition ${
              isSelected
                ? 'border-primary bg-primary text-primary-foreground'
                : 'border-border bg-background text-foreground hover:border-ring'
            }`}
            onClick={() => onSelectCitation(citation)}
          >
            <FileText className="size-3.5 shrink-0" />
            <span className="truncate font-medium">{label}</span>
            <span className="truncate opacity-70">{detail}</span>
          </button>
        )
      })}
    </div>
  )
}

export function MessageList({ messages, isStreaming, runStage, selectedCitation, onSelectCitation }: MessageListProps) {
  if (messages.length === 0) {
    return (
      <div className="grid min-h-full place-items-center px-6 py-12 text-center">
        <div>
          <h1 className="text-2xl font-semibold tracking-normal text-foreground">Start a filing question</h1>
          <p className="mt-3 max-w-md text-sm leading-6 text-muted-foreground">
            Ask about a company, filing year, risk factor, revenue segment, or capex trend.
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
          <p className="whitespace-pre-wrap">{messageBody(message.content, message.role)}</p>
          {message.role === 'assistant' ? (
            <CitationChips
              citations={message.citations ?? []}
              selectedCitation={selectedCitation}
              onSelectCitation={onSelectCitation}
            />
          ) : null}
        </article>
      ))}
      {isStreaming ? <p className="px-1 text-sm text-muted-foreground">{runStage ?? 'Assistant is working...'}</p> : null}
    </div>
  )
}
