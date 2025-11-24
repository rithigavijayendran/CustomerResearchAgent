// WebSocket hook for chat streaming
import { useEffect, useRef, useState, useCallback } from 'react';
import type { WebSocketMessage } from '../types';

interface UseWebSocketOptions {
  chatId: string;
  onToken?: (token: string, text: string) => void;
  onProgress?: (message: string) => void;
  onComplete?: (text: string) => void;
  onError?: (error: string) => void;
  onPlanUpdated?: (planId: string, companyName: string) => void;
}

export function useWebSocket({
  chatId,
  onToken,
  onProgress,
  onComplete,
  onError,
  onPlanUpdated,
}: UseWebSocketOptions) {
  const [isConnected, setIsConnected] = useState(false);
  const [streamingText, setStreamingText] = useState('');
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;
  const currentChatIdRef = useRef<string>('');
  const isIntentionallyDisconnectingRef = useRef(false);
  const connectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(() => {
    // Prevent multiple connections
    if (wsRef.current) {
      const state = wsRef.current.readyState;
      if (state === WebSocket.OPEN || state === WebSocket.CONNECTING) {
        return;
      }
      // Close existing connection if it's in closing/closed state
      try {
        wsRef.current.close();
      } catch (e) {
        // Ignore errors
      }
      wsRef.current = null;
    }

    const token = localStorage.getItem('token');
    if (!token) {
      onError?.('No authentication token');
      return;
    }

    const currentChatId = currentChatIdRef.current;
    if (!currentChatId || currentChatId.trim() === '') {
      return;
    }

    const wsUrl = `${import.meta.env.VITE_WS_URL || 'ws://localhost:8000'}/ws/chats/${currentChatId}/stream?token=${token}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setIsConnected(true);
      reconnectAttempts.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const data: WebSocketMessage = JSON.parse(event.data);
        
        switch (data.type) {
          case 'connected':
            break;
          case 'ping':
            // Respond to keepalive ping
            if (ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: 'pong' }));
            }
            break;
          case 'token':
            if (data.token && data.text) {
              setStreamingText(data.text);
              onToken?.(data.token, data.text);
            }
            break;
          case 'progress':
            if (data.message) {
              onProgress?.(data.message);
            }
            break;
          case 'complete':
            setStreamingText('');
            if (data.text) {
              onComplete?.(data.text);
            } else {
              // Even if no text, call onComplete to clear research state
              onComplete?.('');
            }
            break;
          case 'error':
            if (data.message) {
              onError?.(data.message);
            }
            break;
          case 'plan_updated':
            if (data.planId && data.companyName) {
              onPlanUpdated?.(data.planId, data.companyName);
            }
            break;
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      onError?.('WebSocket connection error');
    };

    ws.onclose = (event) => {
      setIsConnected(false);
      
      // Don't reconnect if it was a normal closure or if intentionally disconnecting
      if (event.code === 1000 || isIntentionallyDisconnectingRef.current) {
        isIntentionallyDisconnectingRef.current = false;
        return;
      }
      
      const currentChatId = currentChatIdRef.current;
      if (!currentChatId || currentChatId.trim() === '') {
        return;
      }
      
      // Attempt to reconnect only if we have a valid chatId
      if (reconnectAttempts.current < maxReconnectAttempts) {
        reconnectAttempts.current++;
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, 1000 * reconnectAttempts.current);
      } else if (reconnectAttempts.current >= maxReconnectAttempts) {
        onError?.('Failed to reconnect after multiple attempts');
      }
    };

    wsRef.current = ws;
  }, [onToken, onProgress, onComplete, onError]);

  const sendMessage = useCallback((message: string, attachments: any[] = []) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ message, attachments }));
    } else {
      onError?.('WebSocket not connected');
    }
  }, [onError]);

  const disconnect = useCallback(() => {
    isIntentionallyDisconnectingRef.current = true;
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (connectTimeoutRef.current) {
      clearTimeout(connectTimeoutRef.current);
      connectTimeoutRef.current = null;
    }
    if (wsRef.current) {
      try {
        wsRef.current.close();
      } catch (e) {
        // Ignore errors
      }
      wsRef.current = null;
    }
    setIsConnected(false);
  }, []);

  useEffect(() => {
    // Update the current chatId ref
    const previousChatId = currentChatIdRef.current;
    currentChatIdRef.current = chatId || '';
    
    // Only connect if we have a valid chatId and it changed
    if (chatId && chatId.trim() !== '' && chatId !== previousChatId) {
      // Disconnect previous connection if chatId changed
      if (previousChatId && previousChatId !== chatId) {
        disconnect();
      }
      
      // Connect immediately for better responsiveness
      connectTimeoutRef.current = setTimeout(() => {
        connect();
      }, 100);
      
      return () => {
        if (connectTimeoutRef.current) {
          clearTimeout(connectTimeoutRef.current);
          connectTimeoutRef.current = null;
        }
        // Only disconnect if chatId is being cleared or changed
        if (!chatId || chatId.trim() === '' || chatId !== currentChatIdRef.current) {
          disconnect();
        }
      };
    } else if (!chatId || chatId.trim() === '') {
      // Disconnect if chatId is empty
      disconnect();
      return () => {};
    } else {
      // chatId hasn't changed, don't do anything
      return () => {};
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatId]);

  // Expose connect function for manual connection attempts
  const manualConnect = useCallback(() => {
    if (currentChatIdRef.current && currentChatIdRef.current.trim() !== '') {
      connect();
    }
  }, [connect]);

  // Helper to check if WebSocket is actually connected (not just state)
  const isActuallyConnected = useCallback(() => {
    return wsRef.current?.readyState === WebSocket.OPEN;
  }, []);

  return {
    isConnected,
    streamingText,
    sendMessage,
    disconnect,
    connect: manualConnect,
    isActuallyConnected,
  };
}

