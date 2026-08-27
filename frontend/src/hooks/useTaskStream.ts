// E4: WebSocket 实时任务进度 hook
// 连接 ws://host/api/v1/ws/tasks/{taskId}?token=xxx，实时接收 Agent 执行事件
import { useEffect, useRef, useCallback, useState } from 'react';
import { getToken } from '../api';

export interface TaskEvent {
  type: 'start' | 'planned' | 'agent_start' | 'agent_done' | 'progress' | 'result' | 'done' | 'error';
  task_id?: string;
  agents?: string[];
  agent?: string;
  status?: string;
  pct?: number;
  result?: unknown;
  error?: string;
}

export interface TaskStreamState {
  events: TaskEvent[];
  agents: string[];          // 已完成的 agent
  plannedAgents: string[];   // planned 事件的全量 agent 清单（计划步骤展示）
  currentAgent: string | null; // 正在执行的 agent
  done: boolean;
  error: string | null;
}

/**
 * 订阅任务实时进度
 * @param taskId 任务 ID（由 coordinator 返回或前端生成）
 * @param enabled 是否启用（默认 true，设 false 可暂停连接）
 * @param onOpen 连接建立回调（可选 — 用于"先连 WS 再发编排请求"避免丢事件）
 */
export function useTaskStream(
  taskId: string | null,
  enabled = true,
  onOpen?: () => void,
): TaskStreamState {
  const [state, setState] = useState<TaskStreamState>({
    events: [],
    agents: [],
    plannedAgents: [],
    currentAgent: null,
    done: false,
    error: null,
  });
  const wsRef = useRef<WebSocket | null>(null);
  const onOpenRef = useRef(onOpen);
  onOpenRef.current = onOpen;

  useEffect(() => {
    if (!taskId || !enabled) return;

    const token = getToken();
    if (!token) return;

    // 构建 WS URL（同源协议，自动 ws/wss 切换）
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${proto}//${location.host}/api/v1/ws/tasks/${taskId}?token=${encodeURIComponent(token)}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => onOpenRef.current?.();

    ws.onmessage = (e) => {
      try {
        const event: TaskEvent = JSON.parse(e.data);
        setState(prev => {
          const agents = [...prev.agents];
          let currentAgent = prev.currentAgent;
          let plannedAgents = prev.plannedAgents;

          if (event.type === 'planned' && Array.isArray(event.agents)) {
            plannedAgents = event.agents.slice();
          }
          if (event.type === 'agent_start') {
            currentAgent = event.agent || null;
          } else if (event.type === 'agent_done') {
            if (event.agent) agents.push(event.agent);
            currentAgent = null;
          }

          return {
            events: [...prev.events, event],
            agents,
            plannedAgents,
            currentAgent,
            done: prev.done || event.type === 'done',
            error: event.type === 'error' ? (event.error || 'Unknown error') : prev.error,
          };
        });
      } catch { /* ignore malformed */ }
    };

    ws.onerror = () => {
      setState(prev => ({ ...prev, error: 'WebSocket connection failed' }));
    };

    ws.onclose = () => {
      wsRef.current = null;
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [taskId, enabled]);

  return state;
}

/** 手动发送 keepalive/ping（可选） */
export function useTaskPing() {
  const wsRef2 = useRef<WebSocket | null>(null);
  return useCallback(() => {
    if (wsRef2.current?.readyState === WebSocket.OPEN) {
      wsRef2.current.send('ping');
    }
  }, []);
}
