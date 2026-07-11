import { ApiError } from '@/lib/http'
import { env } from '@/lib/env'
import { supabase } from '@/lib/supabase'
import { api } from '@/lib/api'

export type ChatThread = {
  id: string
  title: string | null
  created_at: string
  updated_at: string
}

export type ChatMessageRole = 'system' | 'user' | 'assistant'

export type ChatMessage = {
  id: string
  chat_thread_id: string
  role: ChatMessageRole
  content: string
  citations: ChatCitation[]
}

export type ChatCitation = {
  chunk_id: string
  company: string
  filing_type: string
  filing_year: number
  filing_url: string | null
  filing_date: string | null
  report_date: string | null
  section: string | null
  chunk_index: number
  content: string
  neighbor_chunks: string[]
}

export type AiSdkMessage = {
  role: ChatMessageRole
  content: string
}

export async function listThreads() {
  return api.get<ChatThread[]>('/chat/threads')
}

export async function createThread(title?: string) {
  return api.post<ChatThread>('/chat/threads', { title })
}

export async function loadMessages(threadId: string) {
  return api.get<ChatMessage[]>(`/chat/threads/${threadId}/messages`)
}

export async function deleteThread(threadId: string) {
  return api.delete<void>(`/chat/threads/${threadId}`)
}

async function getAccessToken() {
  const { data, error } = await supabase.auth.getSession()

  if (error) {
    throw new ApiError(error.message, { status: 0, data: error, isNetworkError: true })
  }

  return data.session?.access_token ?? null
}

export async function streamChat(
  threadId: string,
  messages: AiSdkMessage[],
  onChunk: (chunk: string) => void,
) {
  const token = await getAccessToken()
  const response = await fetch(`${env.apiBaseUrl}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ thread_id: threadId, messages }),
  })

  if (!response.ok) {
    throw new ApiError(`Request failed with status ${response.status}`, {
      status: response.status,
      data: await response.text(),
    })
  }

  if (!response.body) {
    return
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()

  while (true) {
    const { done, value } = await reader.read()

    if (done) {
      break
    }

    onChunk(decoder.decode(value, { stream: true }))
  }

  const finalChunk = decoder.decode()
  if (finalChunk) {
    onChunk(finalChunk)
  }
}
