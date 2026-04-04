import { useCallback, useEffect, useRef, useState } from 'react'

export function useWebSocket(conversationId, { onBrandCreated } = {}) {
  const [messages, setMessages] = useState([])
  const [status, setStatus] = useState(null)
  const [isTyping, setIsTyping] = useState(false)
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)
  const onBrandCreatedRef = useRef(onBrandCreated)
  onBrandCreatedRef.current = onBrandCreated

  useEffect(() => {
    if (!conversationId) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const ws = new WebSocket(`${protocol}//${host}/ws/chat/${conversationId}`)
    wsRef.current = ws

    ws.onopen = () => setConnected(true)
    ws.onclose = () => {
      setConnected(false)
      setIsTyping(false)
    }

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)

      switch (data.type) {
        case 'message':
          setMessages((prev) => [...prev, { role: data.role, content: data.content }])
          setIsTyping(false)
          break
        case 'image':
          setMessages((prev) => [
            ...prev,
            {
              role: 'assistant',
              content: data.caption,
              image: { jobId: data.job_id, url: data.image_url },
            },
          ])
          setIsTyping(false)
          setStatus(null)
          break
        case 'typing':
          setIsTyping(data.active)
          break
        case 'status':
          setStatus(data.message)
          break
        case 'brand_created':
          if (onBrandCreatedRef.current) {
            onBrandCreatedRef.current(data.brand_id, data.brand_name)
          }
          break
        case 'error':
          console.error('WebSocket error:', data.message)
          setStatus(null)
          setIsTyping(false)
          break
      }
    }

    return () => ws.close()
  }, [conversationId])

  const sendMessage = useCallback(
    (content) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        setMessages((prev) => [...prev, { role: 'user', content }])
        wsRef.current.send(JSON.stringify({ content }))
      }
    },
    []
  )

  return { messages, sendMessage, isTyping, status, connected }
}
