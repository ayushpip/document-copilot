import { ExternalLink, FileText } from 'lucide-react'

import type { ChatCitation } from '@/lib/chat-api'

type SourcePassagePanelProps = {
  citation: ChatCitation | null
}

function formatDate(value: string | null) {
  if (!value) {
    return null
  }
  return new Date(value).toLocaleDateString()
}

export function SourcePassagePanel({ citation }: SourcePassagePanelProps) {
  return (
    <aside className="hidden min-h-0 border-l border-border bg-muted/20 lg:flex lg:flex-col">
      <div className="border-b border-border px-4 py-3">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <FileText className="size-4" />
          Source passage
        </div>
      </div>

      {!citation ? (
        <div className="grid min-h-0 flex-1 place-items-center px-5 text-center">
          <div>
            <p className="text-sm font-medium text-foreground">Select a citation</p>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Click a citation chip on an assistant message to inspect the exact filing passage.
            </p>
          </div>
        </div>
      ) : (
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
          <div className="space-y-1 text-sm">
            <p className="font-semibold text-foreground">
              {citation.company} {citation.filing_type} {citation.filing_year}
            </p>
            <p className="text-xs text-muted-foreground">
              {citation.section ? `${citation.section} · ` : ''}chunk {citation.chunk_index}
              {formatDate(citation.filing_date) ? ` · filed ${formatDate(citation.filing_date)}` : ''}
            </p>
            {citation.filing_url ? (
              <a
                className="inline-flex items-center gap-1 text-xs font-medium text-foreground underline-offset-4 hover:underline"
                href={citation.filing_url}
                target="_blank"
                rel="noreferrer"
              >
                Open SEC filing
                <ExternalLink className="size-3" />
              </a>
            ) : null}
          </div>

          <div className="mt-4 space-y-3">
            <section className="rounded-md border border-border bg-background p-3">
              <p className="mb-2 text-xs font-medium uppercase text-muted-foreground">Selected excerpt</p>
              <p className="whitespace-pre-wrap text-sm leading-6 text-foreground">{citation.content}</p>
            </section>

            {citation.neighbor_chunks.length > 0 ? (
              <section className="rounded-md border border-border bg-background p-3">
                <p className="mb-2 text-xs font-medium uppercase text-muted-foreground">Surrounding context</p>
                <div className="space-y-3">
                  {citation.neighbor_chunks.map((chunk, index) => (
                    <p key={`${citation.chunk_id}-${index}`} className="whitespace-pre-wrap text-sm leading-6 text-muted-foreground">
                      {chunk}
                    </p>
                  ))}
                </div>
              </section>
            ) : null}
          </div>
        </div>
      )}
    </aside>
  )
}
