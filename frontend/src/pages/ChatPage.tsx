import { useEffect, useMemo, useState } from 'react'
import { LogOut } from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'

import { MessageComposer } from '@/components/chat/MessageComposer'
import { MessageList, type DisplayMessage } from '@/components/chat/MessageList'
import { ThreadSidebar } from '@/components/chat/ThreadSidebar'
import { Button } from '@/components/ui/button'
import {
  createThread,
  listThreads,
  loadMessages,
  streamChat,
  type AiSdkMessage,
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

function toDisplayMessages(messages: { id: string; role: DisplayMessage['role']; content: string }[]) {
  return messages.map((message) => ({
    id: message.id,
    role: message.role,
    content: message.content,
  }))
}

export function ChatPage() {
  const { threadId = null } = useParams()
  const navigate = useNavigate()
  const { user, signOut } = useAuth()
  const [threads, setThreads] = useState<ChatThread[]>([])
  const [messages, setMessages] = useState<DisplayMessage[]>([])
  const [isLoadingThreads, setIsLoadingThreads] = useState(true)
  const [status, setStatus] = useState<ChatStatus>({ state: 'idle' })

  async function refreshThreads() {
    setIsLoadingThreads(true)
    try {
      setThreads(await listThreads())
    } finally {
      setIsLoadingThreads(false)
    }
  }

  async function handleNewThread() {
    const thread = await createThread()
    setThreads((current) => [thread, ...current])
    navigate(`/chat/${thread.id}`)
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
      })
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
          message: error instanceof Error ? error.message : 'Unable to load this chat.',
        })
      })

    return () => {
      isMounted = false
    }
  }, [threadId])

  const aiMessages = useMemo<AiSdkMessage[]>(
    () =>
      messages
        .filter((message) => message.role === 'user' || message.role === 'assistant')
        .map((message) => ({ role: message.role, content: message.content })),
    [messages],
  )

  async function handleSend(content: string) {
    setStatus({ state: 'streaming' })
    const activeThread = threadId ? { id: threadId } : await createThread()

    if (!threadId) {
      await refreshThreads()
      navigate(`/chat/${activeThread.id}`, { replace: true })
    }

    const userMessage: DisplayMessage = { id: crypto.randomUUID(), role: 'user', content }
    const assistantMessage: DisplayMessage = { id: crypto.randomUUID(), role: 'assistant', content: '' }
    const nextMessages = [...messages, userMessage, assistantMessage]
    setMessages(nextMessages)

    try {
      await streamChat(activeThread.id, [...aiMessages, { role: 'user', content }], (chunk) => {
        assistantMessage.content += chunk
        setMessages((current) =>
          current.map((message) => (message.id === assistantMessage.id ? { ...assistantMessage } : message)),
        )
      })

      const persistedMessages = await loadMessages(activeThread.id)
      setMessages(toDisplayMessages(persistedMessages))
      await refreshThreads()
      setStatus({ state: 'idle' })
    } catch (error) {
      if (error instanceof ApiError && error.status === 403) {
        setStatus({ state: 'forbidden' })
        return
      }

      setStatus({
        state: 'error',
        message: error instanceof Error ? error.message : 'Unable to send this message.',
      })
    }
  }

  return (
    <main className="grid h-svh grid-cols-[280px_1fr] bg-background text-foreground">
      <ThreadSidebar
        threads={threads}
        activeThreadId={threadId}
        isLoading={isLoadingThreads}
        onNewThread={() => void handleNewThread()}
        onRefresh={() => void refreshThreads()}
      />

      <section className="flex min-w-0 flex-col">
        <header className="flex h-14 items-center justify-between border-b border-border px-5">
          <div className="min-w-0 text-left">
            <p className="truncate text-sm font-semibold">Document Copilot</p>
            <p className="truncate text-xs text-muted-foreground">{user?.email ?? 'Signed in analyst'}</p>
          </div>
          <Button variant="outline" onClick={() => void signOut()}>
            <LogOut />
            Sign out
          </Button>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {status.state === 'forbidden' ? (
            <div className="grid min-h-full place-items-center px-6 text-center">
              <div>
                <h1 className="text-2xl font-semibold tracking-normal text-foreground">Access denied</h1>
                <p className="mt-3 text-sm text-muted-foreground">This thread belongs to another user.</p>
              </div>
            </div>
          ) : null}
          {status.state !== 'forbidden' ? <MessageList messages={messages} isStreaming={status.state === 'streaming'} /> : null}
        </div>

        {status.state === 'error' ? (
          <p className="border-t border-border px-4 py-2 text-sm text-destructive">{status.message}</p>
        ) : null}

        <MessageComposer disabled={status.state === 'loading' || status.state === 'streaming'} onSubmit={handleSend} />
      </section>
    </main>
  )
}
