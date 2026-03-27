"use client";

import { useCallback, useEffect, useRef, useState } from 'react';
import { io, Socket } from 'socket.io-client';
import { useAuthStore } from '@/lib/store/auth-store';

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:3001';

interface UseSocketOptions {
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Error) => void;
}

export function useSocket(options: UseSocketOptions = {}) {
  const [isConnected, setIsConnected] = useState(false);
  const socketRef = useRef<Socket | null>(null);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  // Buffer thread joins so they can be replayed after a reconnect
  const joinedThreads = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!isAuthenticated) {
      socketRef.current?.disconnect();
      socketRef.current = null;
      return;
    }

    const token = typeof document !== 'undefined'
      ? document.cookie.match(/app_jwt=([^;]+)/)?.[1]
      : undefined;

    const socket = io(WS_URL, {
      withCredentials: true,
      transports: ['websocket', 'polling'],
      auth: { token: token || '' },
    });

    socketRef.current = socket;

    socket.on('connect', () => {
      setIsConnected(true);
      // Re-join any threads that were requested before/during reconnect
      joinedThreads.current.forEach((threadId) => {
        socket.emit('thread:join', { threadId });
      });
      options.onConnect?.();
    });

    socket.on('disconnect', () => {
      setIsConnected(false);
      options.onDisconnect?.();
    });

    socket.on('connect_error', (error) => {
      options.onError?.(error as Error);
    });

    return () => {
      socket.disconnect();
      socketRef.current = null;
    };
  }, [isAuthenticated]);

  const joinThread = useCallback((threadId: string) => {
    joinedThreads.current.add(threadId);
    socketRef.current?.emit('thread:join', { threadId });
  }, []);

  const leaveThread = useCallback((threadId: string) => {
    joinedThreads.current.delete(threadId);
    socketRef.current?.emit('thread:leave', { threadId });
  }, []);

  const sendTyping = useCallback((threadId: string) => {
    socketRef.current?.emit('message.typing', { threadId });
  }, []);

  // Stable references — always operate on the current socket instance
  const on = useCallback((event: string, handler: (...args: any[]) => void) => {
    socketRef.current?.on(event, handler);
  }, []);

  const off = useCallback((event: string, handler: (...args: any[]) => void) => {
    socketRef.current?.off(event, handler);
  }, []);

  return {
    socket: socketRef.current,
    isConnected,
    joinThread,
    leaveThread,
    sendTyping,
    on,
    off,
  };
}
