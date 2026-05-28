import axios from 'axios';
import { queryOptions, useQuery } from '@tanstack/react-query';

const actuatorClient = axios.create({ baseURL: '/actuator', timeout: 5_000 });

interface ActuatorMetricResponse {
  name: string;
  measurements: { statistic: string; value: number }[];
}

async function fetchQueueDepth(queue: string): Promise<number> {
  const res = await actuatorClient.get<ActuatorMetricResponse>(
    `/metrics/redis.queue.size?tag=queue:${queue}`,
  );
  return res.data.measurements.find((m) => m.statistic === 'VALUE')?.value ?? 0;
}

const metricsQueries = {
  all: () => ['metrics'] as const,
  queueDepth: (queue: string) =>
    queryOptions({
      queryKey: [...metricsQueries.all(), 'queue', queue] as const,
      queryFn: () => fetchQueueDepth(queue),
      refetchInterval: 15_000,
      staleTime: 10_000,
    }),
};

export function useCrawlerQueueQuery() {
  return useQuery(metricsQueries.queueDepth('posts:queue'));
}

export function useDlqDepthQuery() {
  return useQuery(metricsQueries.queueDepth('posts:dlq'));
}

export function useProcessingQueueQuery() {
  return useQuery(metricsQueries.queueDepth('posts:processing'));
}

export function useCorruptQueueQuery() {
  return useQuery(metricsQueries.queueDepth('posts:corrupt'));
}
