import { LogOut, MessageSquarePlus, PanelLeftClose, PanelLeftOpen, RefreshCw, Trash2, UserCircle } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import type { ChatThread } from '@/lib/chat-api'

type ThreadSidebarProps = {
  threads: ChatThread[]
  activeThreadId: string | null
  isLoading: boolean
  isBusy: boolean
  isCollapsed: boolean
  userEmail: string | null
  onToggleCollapsed: () => void
  onNewThread: () => void
  onRefresh: () => void
  onDeleteThread: (threadId: string) => void
  onSignOut: () => void
}

export function ThreadSidebar({
  threads,
  activeThreadId,
  isLoading,
  isBusy,
  isCollapsed,
  userEmail,
  onToggleCollapsed,
  onNewThread,
  onRefresh,
  onDeleteThread,
  onSignOut,
}: ThreadSidebarProps) {
  return (
    <aside className="flex min-h-0 flex-col border-r border-border bg-muted/25">
      <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-3">
        <div className="flex min-w-0 items-center gap-2 text-sm font-semibold">
          <Button variant="ghost" size="icon-sm" onClick={onToggleCollapsed} aria-label={isCollapsed ? 'Open sidebar' : 'Collapse sidebar'}>
            {isCollapsed ? <PanelLeftOpen /> : <PanelLeftClose />}
          </Button>
          {!isCollapsed ? <span className="truncate">Document Copilot</span> : null}
        </div>
        <div className="flex items-center gap-1">
          {!isCollapsed ? (
            <Button variant="ghost" size="icon-sm" onClick={onRefresh} disabled={isBusy} aria-label="Refresh threads">
              <RefreshCw />
            </Button>
          ) : null}
          <Button variant="default" size="icon-sm" onClick={onNewThread} disabled={isBusy} aria-label="New chat" title="New chat">
            <MessageSquarePlus />
          </Button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {isLoading ? (
          <div className="space-y-2 px-1 py-2">
            {Array.from({ length: 5 }).map((_, index) => (
              <div key={index} className="h-10 animate-pulse rounded-md bg-background" />
            ))}
          </div>
        ) : null}
        {!isLoading && threads.length === 0 ? (
          <div className="px-2 py-3 text-sm text-muted-foreground">
            {isCollapsed ? <span className="sr-only">No conversations yet.</span> : 'No conversations yet.'}
          </div>
        ) : null}
        <nav className="space-y-1" aria-label="Conversation history">
          {threads.map((thread) => (
            <div
              key={thread.id}
              className={`group grid items-center rounded-md transition ${
                isCollapsed ? 'grid-cols-1' : 'grid-cols-[minmax(0,1fr)_auto]'
              } ${
                activeThreadId === thread.id
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:bg-background/70 hover:text-foreground'
              }`}
            >
              <Link
                to={`/chat/${thread.id}`}
                className={`min-w-0 text-left text-sm ${isCollapsed ? 'flex h-9 items-center justify-center px-2' : 'px-3 py-2'}`}
                aria-current={activeThreadId === thread.id ? 'page' : undefined}
                title={thread.title ?? 'New chat'}
              >
                {isCollapsed ? (
                  <span className="font-medium">{(thread.title ?? 'New chat').slice(0, 1).toUpperCase()}</span>
                ) : (
                  <>
                    <span className="block truncate font-medium">{thread.title ?? 'New chat'}</span>
                    <span className="mt-1 block text-xs text-muted-foreground">{new Date(thread.updated_at).toLocaleString()}</span>
                  </>
                )}
              </Link>
              {!isCollapsed ? (
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
              ) : null}
            </div>
          ))}
        </nav>
      </div>

      <div className="border-t border-border p-2">
        {!isCollapsed ? (
          <div className="mb-2 rounded-md border border-border bg-background px-3 py-2">
            <div className="flex items-center gap-2">
              <UserCircle className="size-4 shrink-0 text-muted-foreground" />
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">Signed in</p>
                <p className="truncate text-xs text-muted-foreground">{userEmail ?? 'Analyst'}</p>
              </div>
            </div>
          </div>
        ) : null}
        <div className={isCollapsed ? 'grid gap-1' : 'flex items-center gap-1'}>
          {isCollapsed ? (
            <Button variant="ghost" size="icon-sm" onClick={onRefresh} disabled={isBusy} aria-label="Refresh threads" title="Refresh threads">
            <RefreshCw />
            </Button>
          ) : null}
          <Button variant="outline" className={isCollapsed ? '' : 'w-full justify-start'} onClick={onSignOut} aria-label="Sign out" title="Sign out">
            <LogOut />
            {!isCollapsed ? <span>Sign out</span> : null}
          </Button>
        </div>
      </div>
    </aside>
  )
}
