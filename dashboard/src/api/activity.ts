import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from './client';

export interface ActivityEntry {
  id: number;
  eventType: string;
  message: string;
  occurredAt: string;
}

const activityQueries = {
  all: () => ['activity'] as const,
  recent: () =>
    queryOptions({
      queryKey: [...activityQueries.all(), 'recent'] as const,
      queryFn: async () => {
        const res = await apiClient.get<ActivityEntry[]>('/activity');
        return res.data;
      },
      refetchInterval: 30_000,
      staleTime: 15_000,
    }),
};

export function useActivityQuery() {
  return useQuery(activityQueries.recent());
}

export function useLogActivityMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { eventType: string; message: string }) => {
      await apiClient.post('/activity', payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: activityQueries.all() });
    },
  });
}
