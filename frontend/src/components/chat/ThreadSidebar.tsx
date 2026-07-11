import { MessageSquarePlus, PanelLeft, RefreshCw, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import type { ChatThread } from '@/lib/chat-api'

type ThreadSidebarProps = {
  threads: ChatThread[]
  activeThreadId: string | null
  isLoading: boolean
  isBusy: boolean
  onNewThread: () => void
  onRefresh: () => void
  onDeleteThread: (threadId: string) => void
}

export function ThreadSidebar({
  threads,
  activeThreadId,
  isLoading,
  isBusy,
  onNewThread,
  onRefresh,
  onDeleteThread,
}: ThreadSidebarProps) {
  return (
    <aside className="flex min-h-0 flex-col border-r border-border bg-muted/30">
      <div className="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <PanelLeft className="size-4" />
          Threads
        </div>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon-sm" onClick={onRefresh} disabled={isBusy} aria-label="Refresh threads">
            <RefreshCw />
          </Button>
          <Button variant="default" size="icon-sm" onClick={onNewThread} disabled={isBusy} aria-label="New chat">
            <MessageSquarePlus />
          </Button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {isLoading ? <p className="px-2 py-3 text-sm text-muted-foreground">Loading threads...</p> : null}
        {!isLoading && threads.length === 0 ? (
          <p className="px-2 py-3 text-sm text-muted-foreground">No conversations yet.</p>
        ) : null}
        <nav className="space-y-1">
          {threads.map((thread) => (
            <div
              key={thread.id}
              className={`group grid grid-cols-[minmax(0,1fr)_auto] items-center rounded-md transition ${
                activeThreadId === thread.id
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:bg-background/70 hover:text-foreground'
              }`}
            >
              <Link to={`/chat/${thread.id}`} className="min-w-0 px-3 py-2 text-left text-sm">
                <span className="block truncate font-medium">{thread.title ?? 'New chat'}</span>
                <span className="mt-1 block text-xs text-muted-foreground">{new Date(thread.updated_at).toLocaleString()}</span>
              </Link>
              <Button
                variant="ghost"
                size="icon-sm"
                className="mr-1 opacity-0 transition group-hover:opacity-100 focus:opacity-100"
                disabled={isBusy}
                onClick={() => onDeleteThread(thread.id)}
                aria-label={`Delete ${thread.title ?? 'chat'}`}
              >
                <Trash2 />
              </Button>
            </div>
          ))}
        </nav>
      </div>
    </aside>
  )
}
