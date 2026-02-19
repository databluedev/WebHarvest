import { useEffect, useRef, useCallback } from "react";
import { api, API_BASE_URL } from "@/lib/api";

interface JobSSEUpdate {
  status: string;
  completed_pages: number;
  total_pages: number;
  done?: boolean;
}

/**
 * Hook that listens to SSE for real-time job status updates.
 * Falls back to polling if SSE connection fails.
 *
 * @param jobId - The job ID to listen to
 * @param onUpdate - Called when a status update arrives (triggers data refetch)
 * @param isActive - Whether the job is still active (stop listening when done)
 */
export function useJobSSE(
  jobId: string | null,
  onUpdate: (update: JobSSEUpdate) => void,
  isActive: boolean,
) {
  const eventSourceRef = useRef<EventSource | null>(null);
  const fallbackIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const cleanup = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (fallbackIntervalRef.current) {
      clearInterval(fallbackIntervalRef.current);
      fallbackIntervalRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!jobId || !isActive) {
      cleanup();
      return;
    }

    const token = api.getToken();
    if (!token) return;

    const url = `${API_BASE_URL}/v1/jobs/${jobId}/events?token=${encodeURIComponent(token)}`;

    try {
      const es = new EventSource(url);
      eventSourceRef.current = es;

      es.onmessage = (event) => {
        try {
          const data: JobSSEUpdate = JSON.parse(event.data);
          onUpdate(data);
          if (data.done) {
            es.close();
            eventSourceRef.current = null;
          }
        } catch {}
      };

      es.onerror = () => {
        // SSE failed — fall back to polling
        es.close();
        eventSourceRef.current = null;

        if (!fallbackIntervalRef.current && isActive) {
          fallbackIntervalRef.current = setInterval(() => {
            onUpdate({ status: "__poll__", completed_pages: 0, total_pages: 0 });
          }, 2000);
        }
      };
    } catch {
      // EventSource not supported — fall back to polling
      if (!fallbackIntervalRef.current) {
        fallbackIntervalRef.current = setInterval(() => {
          onUpdate({ status: "__poll__", completed_pages: 0, total_pages: 0 });
        }, 2000);
      }
    }

    return cleanup;
  }, [jobId, isActive, cleanup]);
}
