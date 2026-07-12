import { FileText } from 'lucide-react'

import { AssistantAnswer } from '@/components/chat/AssistantAnswer'
import { ChatEmptyState } from '@/components/chat/ChatEmptyState'
import { RunStatusTimeline } from '@/components/chat/RunStatusTimeline'
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
  runStages: string[]
  isBusy: boolean
  selectedCitation: ChatCitation | null
  onSelectCitation: (citation: ChatCitation) => void
  onSelectPrompt: (prompt: string) => void
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

export function MessageList({
  messages,
  isStreaming,
  runStage,
  runStages,
  isBusy,
  selectedCitation,
  onSelectCitation,
  onSelectPrompt,
}: MessageListProps) {
  if (messages.length === 0) {
    return <ChatEmptyState disabled={isBusy} onSelectPrompt={onSelectPrompt} />
  }

  return (
    <div className="mx-auto max-w-4xl space-y-5 px-4 py-6 sm:px-6">
      {messages.map((message) => (
        <article
          key={message.id}
          className={`rounded-lg border px-4 py-3 text-sm leading-6 shadow-sm ${
            message.role === 'user'
              ? 'ml-auto max-w-2xl border-primary bg-primary text-primary-foreground'
              : 'max-w-3xl border-border bg-card text-card-foreground'
          }`}
        >
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-current opacity-60">{message.role}</p>
          {message.role === 'assistant' ? (
            <AssistantAnswer content={messageBody(message.content, message.role)} />
          ) : (
            <p className="whitespace-pre-wrap">{message.content}</p>
          )}
          {message.role === 'assistant' ? (
            <CitationChips
              citations={message.citations ?? []}
              selectedCitation={selectedCitation}
              onSelectCitation={onSelectCitation}
            />
          ) : null}
        </article>
      ))}
      {isStreaming ? <RunStatusTimeline stages={runStages} activeStage={runStage} /> : null}
    </div>
  )
}
