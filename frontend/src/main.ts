// Minimal client: conversations list, chat view, polling
import '../tailwind.css'
import { marked } from 'marked'


type Conversation = { id: number; title: string | null; created_at: string; updated_at: string }
type Feedback = {
  id: number
  rating: boolean
  note: string | null
  created_at: string
  updated_at: string
}

type Message = {
  id: number
  conversation: number
  role: 'user' | 'ai'
  text: string
  created_at: string
  sequence: number
  feedback?: Feedback | null
  tempId?: string
  pending?: boolean
}

const root = document.getElementById('root')!

type Insights = {
  usage: {
    total_conversations: number
    total_messages: number
    total_user_messages: number
    total_ai_messages: number
  }
  feedback: {
    total_feedback: number
    positive_feedback: number
    negative_feedback: number
    satisfaction_rate: number
    feedback_rate: number
  }
  themes: Array<{ word: string; count: number }>
  quality_scores: {
    average: number | null
    distribution: {
      excellent: number
      good: number
      fair: number
      poor: number
    }
    conversations: Array<{
      id: number
      title: string | null
      quality_score: number | null
      total_messages: number
      feedback_count: number
    }>
  }
  summary: string | null
}

const state = {
  conversations: [] as Conversation[],
  current: null as Conversation | null,
  messages: [] as Message[],
  lastSeq: 0,
  pollTimer: 0 as any,
  activeTab: 'conversations' as 'conversations' | 'usage',
  insights: null as Insights | null,
  insightsPollTimer: 0 as any,
}

async function api<T>(url: string, opts: RequestInit = {}): Promise<T> {
  const resp = await fetch(`/api/${url}`, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    ...opts,
  })
  if (!resp.ok) throw new Error(await resp.text())
  return resp.json()
}

async function loadConversations() {
  const data = await api<{ results: Conversation[]; count: number }>(`conversations/?limit=50`)
  state.conversations = data.results
  if (!state.current && state.conversations.length) state.current = state.conversations[0]
  render()
}

async function loadInsights(includeSummary: boolean = true) {
  try {
    const url = includeSummary ? 'insights/' : 'insights/?include_summary=false'
    const data = await api<Insights>(url)
    // Preserve existing summary if we're not including it in this request
    if (!includeSummary && state.insights?.summary) {
      data.summary = state.insights.summary
    }
    state.insights = data
    render()
  } catch (err) {
    // Error loading insights - silently fail
  }
}

function startInsightsPolling() {
  stopInsightsPolling()
  if (state.activeTab === 'usage') {
    // Poll without summary to avoid regenerating it
    state.insightsPollTimer = setInterval(() => loadInsights(false), 5000) // Poll every 5 seconds
  }
}

function stopInsightsPolling() {
  if (state.insightsPollTimer) {
    clearInterval(state.insightsPollTimer)
    state.insightsPollTimer = 0
  }
}

async function createConversation(title?: string) {
  const data = await api<Conversation>('conversations/', {
    method: 'POST',
    body: JSON.stringify({ title }),
  })
  state.conversations.unshift(data)
  state.current = data
  state.messages = []
  state.lastSeq = 0
  render()
}

async function updateConversationTitle(conversationId: number, title: string | null) {
  try {
    const data = await api<Conversation>(`conversations/${conversationId}/`, {
      method: 'PATCH',
      body: JSON.stringify({ title: title || null }),
    })
    // Update in conversations list
    const idx = state.conversations.findIndex(c => c.id === conversationId)
    if (idx >= 0) {
      state.conversations[idx] = data
    }
    // Update current if it's the same conversation
    if (state.current && state.current.id === conversationId) {
      state.current = data
    }
    render()
  } catch (err) {
    alert('Failed to update conversation title. Please try again.')
  }
}

async function loadMessages() {
  if (!state.current) return
  const data = await api<{ results: Message[]; lastSeq: number }>(
    `conversations/${state.current.id}/messages/?since=${state.lastSeq}`
  )
  if (data.results.length) {
    const existingIds = new Set(state.messages.filter(m => m.id > 0).map(m => m.id))
    const newMessages: Message[] = []
    
    for (const msg of data.results) {
      if (!existingIds.has(msg.id)) {
        const optimisticIdx = state.messages.findIndex(m => 
          (m.id === -1 || m.pending || m.tempId) && m.text === msg.text && m.role === msg.role
        )
        if (optimisticIdx >= 0) {
          state.messages[optimisticIdx] = msg
        } else {
          newMessages.push(msg)
        }
      }
    }
    
    if (newMessages.length) {
      state.messages.push(...newMessages)
      state.messages.sort((a, b) => (a.sequence || 0) - (b.sequence || 0))
      render()
      scrollChatToBottom()
    }
    state.lastSeq = data.lastSeq
  }
}

async function sendMessage(text: string) {
  if (!state.current) return
  const tempId = `tmp-${Date.now()}`
  const optimistic: Message = {
    id: -1,
    conversation: state.current.id,
    role: 'user',
    text,
    created_at: new Date().toISOString(),
    sequence: 0,
    tempId,
    pending: true,
  }
  state.messages.push(optimistic)
  render()
  scrollChatToBottom()

  try {
    const res = await api<{ user_message: Message; ai_message: Message }>(
      `conversations/${state.current.id}/messages/`,
      {
        method: 'POST',
        body: JSON.stringify({ text }),
      }
    )
    const optimisticIdx = state.messages.findIndex((m) => m.tempId === tempId)
    if (optimisticIdx >= 0) state.messages.splice(optimisticIdx, 1)
    
    const existingIds = new Set(state.messages.filter(m => m.id > 0).map(m => m.id))
    const userMsgIdx = state.messages.findIndex(m => m.id === res.user_message.id)
    
    if (userMsgIdx >= 0) {
      state.messages[userMsgIdx] = res.user_message
    } else {
      state.messages.push(res.user_message)
    }
    
    if (!existingIds.has(res.ai_message.id)) {
      state.messages.push(res.ai_message)
    }
    
    state.messages.sort((a, b) => (a.sequence || 0) - (b.sequence || 0))
    state.lastSeq = res.ai_message.sequence
    
    // Refresh conversation to get updated title if it was auto-generated
    if (state.current) {
      try {
        const updatedConv = await api<Conversation>(`conversations/${state.current.id}/`)
        const idx = state.conversations.findIndex(c => c.id === updatedConv.id)
        if (idx >= 0) state.conversations[idx] = updatedConv
        if (state.current.id === updatedConv.id) state.current = updatedConv
      } catch {
        // Non-critical, continue anyway
      }
    }
    
    render()
    scrollChatToBottom()
  } catch (err) {
    const idx = state.messages.findIndex((m) => m.tempId === tempId)
    if (idx >= 0) state.messages.splice(idx, 1)
    render()
    alert('Failed to send message. Please try again.')
  }
}

async function submitFeedback(messageId: number, rating: boolean, note?: string) {
  try {
    const feedback = await api<Feedback>(
      `messages/${messageId}/feedback/`,
      {
        method: 'POST',
        body: JSON.stringify({ rating, note: note || null }),
      }
    )
    // Update the message in state with the feedback
    const msg = state.messages.find((m) => m.id === messageId)
    if (msg) {
      msg.feedback = feedback
      preserveScrollPosition(() => render())
    }
    // Refresh insights if on usage tab (without summary to avoid regenerating)
    if (state.activeTab === 'usage') {
      loadInsights(false)
    }
  } catch (err) {
    alert('Failed to submit feedback. Please try again.')
  }
}

function startPolling() {
  stopPolling()
  state.pollTimer = setInterval(loadMessages, 3000)
}
function stopPolling() {
  if (state.pollTimer) clearInterval(state.pollTimer)
}

function scrollChatToBottom() {
  const c = document.getElementById('chat-scroll')
  if (c) c.scrollTop = c.scrollHeight
}

function preserveScrollPosition(callback: () => void) {
  const chatScroll = document.getElementById('chat-scroll')
  if (!chatScroll) {
    callback()
    return
  }
  
  const scrollTop = chatScroll.scrollTop
  const scrollHeight = chatScroll.scrollHeight
  const clientHeight = chatScroll.clientHeight
  const wasAtBottom = scrollHeight - scrollTop - clientHeight < 50 // 50px threshold
  
  callback()
  
  // Use setTimeout to ensure DOM is updated
  setTimeout(() => {
    const newChatScroll = document.getElementById('chat-scroll')
    if (newChatScroll) {
      if (wasAtBottom) {
        // If was at bottom, scroll to new bottom
        newChatScroll.scrollTop = newChatScroll.scrollHeight
      } else {
        // Otherwise, try to restore relative position
        const newScrollHeight = newChatScroll.scrollHeight
        const heightDiff = newScrollHeight - scrollHeight
        newChatScroll.scrollTop = scrollTop + heightDiff
      }
    }
  }, 0)
}

function render() {
  root.innerHTML = `
  <div class="mx-auto max-w-6xl p-4" style="min-height: 100vh;">
    <div class="mb-2 win-panel p-2">
      <div class="flex gap-1">
        <button 
          id="tab-conversations"
          class="win-tab ${state.activeTab === 'conversations' ? 'win-tab-active' : ''} px-4 py-2 font-medium"
        >
          Conversations
        </button>
        <button 
          id="tab-usage"
          class="win-tab ${state.activeTab === 'usage' ? 'win-tab-active' : ''} px-4 py-2 font-medium"
        >
          Usage
        </button>
      </div>
    </div>
    ${state.activeTab === 'conversations' ? renderConversations() : renderUsage()}
  </div>`
  
  // Attach event listeners
  attachEventListeners()
}

function renderConversations() {
  return `
  <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
    <aside class="md:col-span-1 space-y-2">
      <div class="win-panel p-2">
        <div class="flex gap-2 items-center mb-2">
          <button id="new-conv" class="btn btn-primary">New Conversation</button>
        </div>
        <div class="win-panel-inset p-1">
          <ul class="divide-y divide-gray-300" style="max-height: 60vh; overflow-y: auto;">
            ${state.conversations
              .map(
                (c) => `
              <li class="p-1 ${state.current?.id === c.id ? 'bg-gradient-to-r from-purple-200 to-pink-200' : 'hover:bg-gradient-to-r hover:from-purple-100 hover:to-pink-100'}">
                <button data-cid="${c.id}" class="w-full text-left text-sm text-primary">
                  ${escapeHtml(c.title ?? 'Untitled')}<br>
                  <span class="text-xs text-secondary">${new Date(c.updated_at).toLocaleString()}</span>
                </button>
              </li>
            `
              )
              .join('')}
          </ul>
        </div>
      </div>
    </aside>
    <main class="md:col-span-3 flex flex-col h-[80vh]">
      <div class="win-panel p-2 flex flex-col h-full">
        ${state.current ? `
          <div class="mb-2 win-panel-inset p-2">
            <div class="flex items-center gap-2">
              <input 
                id="conversation-title-input"
                type="text"
                value="${escapeHtml(state.current.title || '')}"
                placeholder="Untitled conversation"
                class="input flex-1 text-base font-medium"
                maxlength="200"
              />
              <button 
                id="save-title-btn"
                class="btn btn-primary text-sm hidden"
              >
                Save
              </button>
              <button 
                id="cancel-title-btn"
                class="btn text-sm hidden"
              >
                Cancel
              </button>
            </div>
          </div>
        ` : ''}
        <div id="chat-scroll" class="win-panel-inset flex-1 overflow-auto p-3 space-y-3" style="min-height: 0;">
        ${state.messages
          .map(
            (m) => `
          <div class="p-3 ${m.role === 'user' ? 'msg-user' : 'msg-ai'}">
            <div class="text-xs mb-1 text-secondary">${m.role.toUpperCase()} • ${new Date(m.created_at).toLocaleTimeString()}</div>
            ${m.role === 'ai' 
              ? `<div class="markdown-content text-primary">${renderMarkdown(m.text)}</div>`
              : `<div class="whitespace-pre-wrap text-primary">${escapeHtml(m.text)}</div>`
            }
            ${m.role === 'ai' ? `
              <div class="mt-2 pt-2" style="border-top: 1px solid #C8C4C0;">
                <div class="flex items-center gap-2 mb-2">
                  <span class="text-xs text-tertiary">Was this helpful?</span>
                  <button 
                    data-feedback-btn="${m.id}" 
                    data-rating="true"
                    class="btn ${m.feedback?.rating === true ? 'btn-primary' : ''} px-2 py-1 text-sm"
                    title="Thumbs up"
                  >
                    👍
                  </button>
                  <button 
                    data-feedback-btn="${m.id}" 
                    data-rating="false"
                    class="btn px-2 py-1 text-sm ${m.feedback?.rating === false ? 'btn-negative' : ''}"
                    title="Thumbs down"
                  >
                    👎
                  </button>
                </div>
                ${m.feedback ? `
                  <div class="text-xs mb-1 text-secondary">
                    ${m.feedback.rating ? '👍' : '👎'} Feedback submitted
                    ${m.feedback.note ? ` • Note: ${escapeHtml(m.feedback.note)}` : ''}
                    <button 
                      data-feedback-edit="${m.id}"
                      class="ml-2 text-xs underline text-tertiary"
                    >
                      ${m.feedback.note ? 'Edit note' : 'Add note'}
                    </button>
                  </div>
                ` : ''}
                <div id="feedback-note-${m.id}" class="hidden mt-2">
                  <textarea 
                    id="feedback-note-input-${m.id}" 
                    class="textarea w-full text-sm" 
                    rows="2" 
                    placeholder="Optional: Why was this helpful or not helpful?"
                  >${m.feedback?.note || ''}</textarea>
                  <div class="flex gap-2 mt-1">
                    <button 
                      data-feedback-submit="${m.id}"
                      class="btn btn-primary text-xs"
                    >
                      Submit
                    </button>
                    <button 
                      data-feedback-cancel="${m.id}"
                      class="btn text-xs"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            ` : ''}
          </div>
        `
          )
          .join('')}
      </div>
      <div class="mt-2 win-panel-inset p-2">
        <form id="composer" class="flex gap-2">
          <textarea id="input" class="textarea flex-1" rows="3" placeholder="Type a message (max 1000 chars)"></textarea>
          <button class="btn btn-primary" type="submit">Send</button>
        </form>
      </div>
    </main>
  </div>`
}

function renderUsage() {
  if (!state.insights) {
    return `<div class="win-panel p-4 text-center text-secondary">Loading insights...</div>`
  }
  
  const { usage, feedback, themes, quality_scores, summary } = state.insights
  
  return `
  <div class="space-y-4">
    <div class="win-panel p-3">
      <h1 class="text-2xl font-bold mb-2 text-primary" style="text-shadow: 1px 1px 0px rgba(255, 255, 255, 0.5);">Usage Insights</h1>
    </div>
    
    ${summary ? `
      <div class="win-panel p-4" style="background: linear-gradient(to bottom, #E6F0FF, #F0F6FF); border: 2px inset #D4E6FF;">
        <div class="flex items-start gap-2">
          <span style="font-size: 1.2em;">💡</span>
          <div class="flex-1">
            <div class="text-sm mb-1 text-tertiary font-bold">AI Summary</div>
            <div class="markdown-content text-primary">${renderMarkdown(summary)}</div>
          </div>
        </div>
      </div>
    ` : ''}
    
    <!-- Usage Statistics -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-3">
      <div class="win-panel p-4">
        <div class="text-sm mb-1 text-secondary">Total Conversations</div>
        <div class="text-2xl font-bold text-primary">${usage.total_conversations}</div>
      </div>
      <div class="win-panel p-4">
        <div class="text-sm mb-1 text-secondary">Total Messages</div>
        <div class="text-2xl font-bold text-primary">${usage.total_messages}</div>
      </div>
      <div class="win-panel p-4">
        <div class="text-sm mb-1 text-secondary">User Messages</div>
        <div class="text-2xl font-bold text-primary">${usage.total_user_messages}</div>
      </div>
      <div class="win-panel p-4">
        <div class="text-sm mb-1 text-secondary">AI Messages</div>
        <div class="text-2xl font-bold text-primary">${usage.total_ai_messages}</div>
      </div>
    </div>
    
    <!-- Feedback Statistics -->
    <div class="win-panel p-4">
      <h2 class="text-xl font-semibold mb-3 text-primary">Feedback Statistics</h2>
      <div class="grid grid-cols-1 md:grid-cols-4 gap-3 mb-4">
        <div class="win-panel-inset p-3">
          <div class="text-sm mb-1 text-secondary">Total Feedback</div>
          <div class="text-xl font-bold text-primary">${feedback.total_feedback}</div>
        </div>
        <div class="win-panel-inset p-3">
          <div class="text-sm mb-1 text-secondary">Satisfaction Rate</div>
          <div class="text-xl font-bold text-success">${feedback.satisfaction_rate}%</div>
        </div>
        <div class="win-panel-inset p-3">
          <div class="text-sm mb-1 text-secondary">Feedback Rate</div>
          <div class="text-xl font-bold text-primary">${feedback.feedback_rate}%</div>
        </div>
        <div class="win-panel-inset p-3">
          <div class="text-sm mb-1 text-secondary">Positive / Negative</div>
          <div class="text-xl font-bold">
            <span class="text-success">${feedback.positive_feedback}</span> / 
            <span class="text-error">${feedback.negative_feedback}</span>
          </div>
        </div>
      </div>
      
      <!-- Feedback Breakdown -->
      <div class="mt-3">
        <div class="win-panel-inset p-2">
          <div class="flex items-center gap-2 mb-1">
            <div class="flex-1 win-border-sunken" style="height: 20px; background: #E0DCD8; position: relative; overflow: hidden;">
              <div 
                style="height: 100%; background: linear-gradient(to bottom, #B8E6B8, #A4D4A4); width: ${feedback.total_feedback > 0 ? (feedback.positive_feedback / feedback.total_feedback * 100) : 0}%; transition: width 0.3s;"
              ></div>
            </div>
            <span class="text-sm text-tertiary">${feedback.total_feedback > 0 ? Math.round(feedback.positive_feedback / feedback.total_feedback * 100) : 0}% positive</span>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Quality Scores -->
    <div class="win-panel p-4">
      <h2 class="text-xl font-semibold mb-3 text-primary">Conversation Quality Scores</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="win-panel-inset p-3">
          <div class="text-sm mb-2 text-secondary">Average Quality Score</div>
          <div class="text-3xl font-bold text-primary">
            ${quality_scores.average !== null ? quality_scores.average.toFixed(1) : 'N/A'}
            ${quality_scores.average !== null ? '<span class="text-lg">/ 100</span>' : ''}
          </div>
        </div>
        <div class="win-panel-inset p-3">
          <div class="text-sm mb-2 text-secondary">Quality Distribution</div>
          <div class="grid grid-cols-2 gap-2 text-sm">
            <div>
              <span class="text-success">Excellent (80+):</span> ${quality_scores.distribution.excellent}
            </div>
            <div>
              <span class="text-success" style="opacity: 0.7;">Good (60-79):</span> ${quality_scores.distribution.good}
            </div>
            <div>
              <span style="color: #7A7A2A;">Fair (40-59):</span> ${quality_scores.distribution.fair}
            </div>
            <div>
              <span class="text-error">Poor (&lt;40):</span> ${quality_scores.distribution.poor}
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Feedback Themes -->
    <div class="win-panel p-4">
      <h2 class="text-xl font-semibold mb-3 text-primary">Feedback Themes</h2>
      <div class="win-panel-inset p-2">
        ${themes.length > 0 ? `
          <div class="space-y-1">
            ${themes.map(theme => `
              <div class="win-border-outset p-2 flex items-center justify-between" style="background: linear-gradient(to bottom, #FFF8E6, #FFFBF0);">
                <span class="font-medium text-primary">${escapeHtml(theme.word)}</span>
                <span class="text-sm text-secondary">${theme.count} ${theme.count === 1 ? 'time' : 'times'}</span>
              </div>
            `).join('')}
          </div>
        ` : '<p class="text-secondary">No feedback themes available yet.</p>'}
      </div>
    </div>
  </div>`
}


function attachEventListeners() {
  document.getElementById('new-conv')?.addEventListener('click', () => {
    createConversation()
  })
  
  // Tab switching
  document.getElementById('tab-conversations')?.addEventListener('click', () => {
    stopInsightsPolling()
    state.activeTab = 'conversations'
    render()
  })
  
  document.getElementById('tab-usage')?.addEventListener('click', () => {
    state.activeTab = 'usage'
    if (!state.insights) {
      loadInsights()
    } else {
      render()
    }
    startInsightsPolling()
  })

  // Conversation title editing handlers
  const titleInput = document.getElementById('conversation-title-input') as HTMLInputElement
  const saveTitleBtn = document.getElementById('save-title-btn')
  const cancelTitleBtn = document.getElementById('cancel-title-btn')
  
  const toggleButtons = (show: boolean) => {
    saveTitleBtn?.classList.toggle('hidden', !show)
    cancelTitleBtn?.classList.toggle('hidden', !show)
  }
  
  if (titleInput && state.current) {
    const originalTitle = state.current.title

    titleInput.addEventListener('input', () => {
      toggleButtons(titleInput.value.trim() !== (originalTitle || ''))
    })

    titleInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && saveTitleBtn && !saveTitleBtn.classList.contains('hidden')) {
        e.preventDefault()
        saveTitleBtn.click()
      } else if (e.key === 'Escape' && cancelTitleBtn && !cancelTitleBtn.classList.contains('hidden')) {
        e.preventDefault()
        cancelTitleBtn.click()
      }
    })
  }

  saveTitleBtn?.addEventListener('click', async () => {
    if (!state.current || !titleInput) return
    await updateConversationTitle(state.current.id, titleInput.value.trim() || null)
    toggleButtons(false)
  })

  cancelTitleBtn?.addEventListener('click', () => {
    if (titleInput && state.current) {
      titleInput.value = state.current.title || ''
      toggleButtons(false)
    }
  })
  document.querySelectorAll('[data-cid]')?.forEach((el) => {
    el.addEventListener('click', () => {
      const cid = Number((el as HTMLElement).dataset.cid)
      const c = state.conversations.find((x) => x.id === cid) || null
      state.current = c
      state.messages = []
      state.lastSeq = 0
      render()
      loadMessages()
    })
  })
  
  const form = document.getElementById('composer') as HTMLFormElement
  form?.addEventListener('submit', async (e) => {
    e.preventDefault()
    const input = document.getElementById('input') as HTMLTextAreaElement
    const text = input.value.trim()
    if (!text) return
    if (text.length > 1000) {
      alert('Message too long')
      return
    }
    input.value = ''
    await sendMessage(text)
  })

  // Feedback handlers
  const toggleNoteDiv = (messageId: number, show: boolean) => {
    document.getElementById(`feedback-note-${messageId}`)?.classList.toggle('hidden', !show)
  }

  document.querySelectorAll('[data-feedback-btn]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const messageId = Number((btn as HTMLElement).dataset.feedbackBtn)
      const rating = (btn as HTMLElement).dataset.rating === 'true'
      await submitFeedback(messageId, rating)
      toggleNoteDiv(messageId, true)
    })
  })

  document.querySelectorAll('[data-feedback-submit]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const messageId = Number((btn as HTMLElement).dataset.feedbackSubmit)
      const noteInput = document.getElementById(`feedback-note-input-${messageId}`) as HTMLTextAreaElement
      const note = noteInput?.value.trim() || undefined
      const msg = state.messages.find((m) => m.id === messageId)
      if (msg?.feedback) {
        await submitFeedback(messageId, msg.feedback.rating, note)
      }
      toggleNoteDiv(messageId, false)
    })
  })

  document.querySelectorAll('[data-feedback-cancel]').forEach((btn) => {
    btn.addEventListener('click', () => {
      toggleNoteDiv(Number((btn as HTMLElement).dataset.feedbackCancel), false)
    })
  })

  document.querySelectorAll('[data-feedback-edit]').forEach((btn) => {
    btn.addEventListener('click', () => {
      toggleNoteDiv(Number((btn as HTMLElement).dataset.feedbackEdit), true)
    })
  })
}

function escapeHtml(s: string) {
  return s.replace(
    /[&<>"]/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c] as string
  )
}

function renderMarkdown(text: string): string {
  // Configure marked options
  marked.setOptions({
    breaks: true,
    gfm: true,
  })
  
  // Render markdown to HTML
  let html = marked.parse(text) as string
  
  // Basic HTML sanitization for security
  const temp = document.createElement('div')
  temp.innerHTML = html
  
  // Remove dangerous elements
  const dangerous = temp.querySelectorAll('script, iframe, object, embed, form, input, button, style')
  dangerous.forEach(el => el.remove())
  
  // Remove event handlers and dangerous attributes
  const allElements = temp.querySelectorAll('*')
  allElements.forEach(el => {
    // Remove all event handler attributes
    Array.from(el.attributes).forEach(attr => {
      if (attr.name.toLowerCase().startsWith('on')) {
        el.removeAttribute(attr.name)
      }
    })
    
    // Make external links safe
    if (el.tagName === 'A' && el.getAttribute('href')) {
      const href = el.getAttribute('href') || ''
      if (href.startsWith('http://') || href.startsWith('https://')) {
        el.setAttribute('target', '_blank')
        el.setAttribute('rel', 'noopener noreferrer')
      } else if (!href.startsWith('#')) {
        // Remove unsafe links (javascript:, data:, etc.)
        el.removeAttribute('href')
      }
    }
  })
  
  return temp.innerHTML
}

// Boot
;(async function init() {
  // Inject Tailwind (built via PostCSS)
  const link = document.createElement('link')
  link.rel = 'stylesheet'
  link.href = '/static/app/style.css'
  document.head.appendChild(link)
  await loadConversations()
  await loadMessages()
  startPolling()
})()
