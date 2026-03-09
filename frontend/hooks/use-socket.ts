"use client";

import { useEffect, useRef, useState } from 'react';
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

  useEffect(() => {
    if (!isAuthenticated) {
      if (socketRef.current) {
        socketRef.current.disconnect();
        socketRef.current = null;
      }
      return;
    }

    // Create socket connection
    const socket = io(WS_URL, {
      withCredentials: true,
      transports: ['websocket', 'polling'],
    });

    socketRef.current = socket;

    socket.on('connect', () => {
      setIsConnected(true);
      options.onConnect?.();
    });

    socket.on('disconnect', () => {
      setIsConnected(false);
      options.onDisconnect?.();
    });

    socket.on('connect_error', (error) => {
      console.error('Socket connection error:', error);
      options.onError?.(error as Error);
    });

    return () => {
      socket.disconnect();
      socketRef.current = null;
    };
  }, [isAuthenticated]);

  const joinThread = (threadId: string) => {
    socketRef.current?.emit('thread:join', { threadId });
  };

  const leaveThread = (threadId: string) => {
    socketRef.current?.emit('thread:leave', { threadId });
  };

  const sendTyping = (threadId: string) => {
    socketRef.current?.emit('message.typing', { threadId });
  };

  const on = (event: string, handler: (...args: any[]) => void) => {
    socketRef.current?.on(event, handler);
  };

  const off = (event: string, handler: (...args: any[]) => void) => {
    socketRef.current?.off(event, handler);
  };

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
