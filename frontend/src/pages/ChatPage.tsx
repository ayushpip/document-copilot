import { useEffect, useRef, useState } from 'react'
import { FileText } from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'

import { ChatErrorBanner } from '@/components/chat/ChatErrorBanner'
import { ChatWorkspaceShell } from '@/components/chat/ChatWorkspaceShell'
import { MessageComposer } from '@/components/chat/MessageComposer'
import { MessageList, type DisplayMessage } from '@/components/chat/MessageList'
import { SourcePassagePanel } from '@/components/chat/SourcePassagePanel'
import { ThreadSidebar } from '@/components/chat/ThreadSidebar'
import { Button } from '@/components/ui/button'
import {
  createThread,
  deleteThread,
  listThreads,
  loadMessages,
  streamChat,
  type ChatCitation,
  type ChatThread,
} from '@/lib/chat-api'
import { ApiError } from '@/lib/http'
import { useAuth } from '@/lib/auth-context'

type ChatStatus =
  | { state: 'idle' }
  | { state: 'loading' }
  | { state: 'streaming' }
  | { state: 'error'; message: string }
  | { state: 'forbidden' }

const RUN_STAGES = [
  'Searching filings...',
  'Ranking relevant passages...',
  'Checking source evidence...',
  'Drafting grounded answer...',
  'Validating citations...',
]

function toDisplayMessages(messages: { id: string; role: DisplayMessage['role']; content: string; citations?: ChatCitation[] }[]) {
  return messages.map((message) => ({
    id: message.id,
    role: message.role,
    content: message.content,
    citations: message.citations ?? [],
  }))
}

function errorMessage(error: unknown) {
  if (!(error instanceof ApiError)) {
    return error instanceof Error ? error.message : 'Unable to send this message.'
  }

  if (error.status === 401) {
    return 'Session expired. Please sign in again.'
  }
  if (error.status === 502) {
    return 'The assistant could not validate its citations or evidence. Try rephrasing or narrowing the question.'
  }
  if (error.isNetworkError || error.status === 0) {
    return 'Network or CORS error. Check that the backend is running and reachable.'
  }
  return error.message
}

export function ChatPage() {
  const { threadId = null } = useParams()
  const navigate = useNavigate()
  const { user, signOut } = useAuth()
  const [threads, setThreads] = useState<ChatThread[]>([])
  const [messages, setMessages] = useState<DisplayMessage[]>([])
  const [isLoadingThreads, setIsLoadingThreads] = useState(true)
  const [status, setStatus] = useState<ChatStatus>({ state: 'idle' })
  const [runStage, setRunStage] = useState<string | null>(null)
  const [selectedCitation, setSelectedCitation] = useState<ChatCitation | null>(null)
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false)
  const [isSourcePanelOpen, setIsSourcePanelOpen] = useState(false)
  const activeSendThreadIdRef = useRef<string | null>(null)
  const isBusy = status.state === 'loading' || status.state === 'streaming'

  async function refreshThreads() {
    setIsLoadingThreads(true)
    try {
      setThreads(await listThreads())
    } finally {
      setIsLoadingThreads(false)
    }
  }

  async function handleNewThread() {
    if (isBusy) {
      return
    }

    const thread = await createThread()
    setThreads((current) => [thread, ...current])
    navigate(`/chat/${thread.id}`)
  }

  async function handleDeleteThread(deletedThreadId: string) {
    if (isBusy) {
      return
    }

    const remainingThreads = threads.filter((thread) => thread.id !== deletedThreadId)
    setThreads(remainingThreads)

    if (deletedThreadId === threadId) {
      setMessages([])
      setSelectedCitation(null)
      setIsSourcePanelOpen(false)
      setStatus({ state: 'idle' })
      navigate(remainingThreads[0] ? `/chat/${remainingThreads[0].id}` : '/chat', { replace: true })
    }

    try {
      await deleteThread(deletedThreadId)
      await refreshThreads()
    } catch (error) {
      setStatus({ state: 'error', message: errorMessage(error) })
      await refreshThreads()
    }
  }

  useEffect(() => {
    let isMounted = true

    listThreads()
      .then((loadedThreads) => {
        if (isMounted) {
          setThreads(loadedThreads)
        }
      })
      .finally(() => {
        if (isMounted) {
          setIsLoadingThreads(false)
        }
      })

    return () => {
      isMounted = false
    }
  }, [])

  useEffect(() => {
    if (!threadId) {
      queueMicrotask(() => {
        setMessages([])
        setStatus({ state: 'idle' })
        setSelectedCitation(null)
        setIsSourcePanelOpen(false)
      })
      return
    }

    if (activeSendThreadIdRef.current === threadId) {
      return
    }

    let isMounted = true
    queueMicrotask(() => {
      if (isMounted) {
        setStatus({ state: 'loading' })
      }
    })

    loadMessages(threadId)
      .then((history) => {
        if (isMounted) {
          setMessages(toDisplayMessages(history))
          setStatus({ state: 'idle' })
          setSelectedCitation(null)
          setIsSourcePanelOpen(false)
        }
      })
      .catch((error: unknown) => {
        if (!isMounted) {
          return
        }

        if (error instanceof ApiError && error.status === 403) {
          setStatus({ state: 'forbidden' })
          return
        }

        setStatus({
          state: 'error',
          message: errorMessage(error),
        })
      })

    return () => {
      isMounted = false
    }
  }, [threadId])

  async function handleSend(content: string): Promise<boolean> {
    setStatus({ state: 'streaming' })
    setRunStage(RUN_STAGES[0])
    let stageIndex = 0
    let hasReceivedText = false
    const stageTimer = window.setInterval(() => {
      if (hasReceivedText) {
        return
      }
      stageIndex = Math.min(stageIndex + 1, RUN_STAGES.length - 1)
      setRunStage(RUN_STAGES[stageIndex])
    }, 1800)

    try {
      const activeThread = threadId ? { id: threadId } : await createThread()
      activeSendThreadIdRef.current = activeThread.id

      if (!threadId) {
        setThreads((current) =>
          current.some((thread) => thread.id === activeThread.id)
            ? current
            : [
                {
                  id: activeThread.id,
                  title: null,
                  created_at: new Date().toISOString(),
                  updated_at: new Date().toISOString(),
                },
                ...current,
              ],
        )
        navigate(`/chat/${activeThread.id}`, { replace: true })
      }

      const userMessage: DisplayMessage = { id: crypto.randomUUID(), role: 'user', content }
      const assistantMessage: DisplayMessage = { id: crypto.randomUUID(), role: 'assistant', content: '', citations: [] }
      const nextMessages = [...messages, userMessage, assistantMessage]
      const streamMessages = nextMessages
        .filter((message) => message.role === 'user' || message.role === 'assistant')
        .filter((message) => message.content.trim() !== '')
        .map((message) => ({ role: message.role, content: message.content }))
      setMessages(nextMessages)
      setSelectedCitation(null)
      setIsSourcePanelOpen(false)

      await streamChat(activeThread.id, streamMessages, (chunk) => {
        if (!hasReceivedText) {
          hasReceivedText = true
          window.clearInterval(stageTimer)
          setRunStage('Writing grounded answer...')
        }
        assistantMessage.content += chunk
        setMessages((current) =>
          current.map((message) => (message.id === assistantMessage.id ? { ...assistantMessage } : message)),
        )
      })

      setRunStage('Saving answer...')
      const persistedMessages = await loadMessages(activeThread.id)
      setMessages(toDisplayMessages(persistedMessages))
      await refreshThreads()
      setStatus({ state: 'idle' })
      setRunStage(null)
      activeSendThreadIdRef.current = null
      return true
    } catch (error) {
      window.clearInterval(stageTimer)
      setRunStage(null)
      activeSendThreadIdRef.current = null
      if (error instanceof ApiError && error.status === 403) {
        setStatus({ state: 'forbidden' })
        return false
      }

      setStatus({
        state: 'error',
        message: errorMessage(error),
      })
      return false
    } finally {
      window.clearInterval(stageTimer)
    }
  }

  return (
    <ChatWorkspaceShell
      isSidebarCollapsed={isSidebarCollapsed}
      isSourcePanelOpen={isSourcePanelOpen}
      sidebar={
        <ThreadSidebar
          threads={threads}
          activeThreadId={threadId}
          isLoading={isLoadingThreads}
          isBusy={isBusy}
          isCollapsed={isSidebarCollapsed}
          userEmail={user?.email ?? null}
          onToggleCollapsed={() => setIsSidebarCollapsed((current) => !current)}
          onNewThread={() => void handleNewThread()}
          onRefresh={() => void refreshThreads()}
          onDeleteThread={(deletedThreadId) => void handleDeleteThread(deletedThreadId)}
          onSignOut={() => void signOut()}
        />
      }
      sourcePanel={
        <SourcePassagePanel citation={selectedCitation} isOpen={isSourcePanelOpen} onClose={() => setIsSourcePanelOpen(false)} />
      }
    >
      <section className="flex min-w-0 flex-col">
        <header className="flex h-14 items-center justify-between border-b border-border px-5">
          <div className="min-w-0 text-left">
            <p className="truncate text-sm font-semibold">Document Copilot</p>
            <p className="truncate text-xs text-muted-foreground">Internal analyst workspace</p>
          </div>
          {selectedCitation ? (
            <Button variant="outline" onClick={() => setIsSourcePanelOpen((current) => !current)}>
              <FileText />
              Sources
            </Button>
          ) : null}
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {status.state === 'forbidden' ? (
            <div className="grid min-h-full place-items-center px-6 text-center">
              <div>
                <h1 className="!m-0 !text-2xl font-semibold tracking-normal text-foreground">Access denied</h1>
                <p className="mt-3 text-sm text-muted-foreground">This thread belongs to another user.</p>
              </div>
            </div>
          ) : null}
          {status.state !== 'forbidden' ? (
            <MessageList
              messages={messages}
              isStreaming={status.state === 'streaming'}
              runStage={runStage}
              runStages={RUN_STAGES}
              isBusy={isBusy}
              selectedCitation={selectedCitation}
              onSelectCitation={(citation) => {
                setSelectedCitation(citation)
                setIsSourcePanelOpen(true)
              }}
              onSelectPrompt={(prompt) => void handleSend(prompt)}
            />
          ) : null}
        </div>

        {status.state === 'error' ? <ChatErrorBanner message={status.message} /> : null}

        <MessageComposer disabled={isBusy} onSubmit={handleSend} />
      </section>
    </ChatWorkspaceShell>
  )
}
