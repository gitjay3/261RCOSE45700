import { queryOptions, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from './client';
import type {
  DetectionType,
  NotificationChannel,
  NotificationChannelType,
  NotificationDelivery,
  NotificationRule,
  NotificationTestResponse,
  Tier,
} from '@/types/api';

export interface CreateNotificationChannelInput {
  name: string;
  type: NotificationChannelType;
  webhookUrl: string;
  enabled: boolean;
}

export interface CreateNotificationRuleInput {
  name: string;
  channelId: number;
  enabled: boolean;
  minConfidence: number | null;
  minTier: Tier | null;
  detectionType: DetectionType | null;
  sourceSiteName: string | null;
}

const notificationQueries = {
  all: () => ['notifications'] as const,
  channels: () =>
    queryOptions({
      queryKey: [...notificationQueries.all(), 'channels'] as const,
      queryFn: async () => {
        const response = await apiClient.get<NotificationChannel[]>('/notifications/channels');
        return response.data;
      },
      staleTime: 10_000,
    }),
  rules: () =>
    queryOptions({
      queryKey: [...notificationQueries.all(), 'rules'] as const,
      queryFn: async () => {
        const response = await apiClient.get<NotificationRule[]>('/notifications/rules');
        return response.data;
      },
      staleTime: 10_000,
    }),
  deliveries: () =>
    queryOptions({
      queryKey: [...notificationQueries.all(), 'deliveries'] as const,
      queryFn: async () => {
        const response = await apiClient.get<NotificationDelivery[]>('/notifications/deliveries');
        return response.data;
      },
      refetchInterval: 10_000,
      staleTime: 5_000,
    }),
};

export function useNotificationChannelsQuery() {
  return useQuery(notificationQueries.channels());
}

export function useNotificationRulesQuery() {
  return useQuery(notificationQueries.rules());
}

export function useNotificationDeliveriesQuery() {
  return useQuery(notificationQueries.deliveries());
}

export function useCreateNotificationChannelMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: CreateNotificationChannelInput) => {
      const response = await apiClient.post<NotificationChannel>('/notifications/channels', input);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: notificationQueries.all() });
    },
  });
}

export function useTestNotificationChannelMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      const response = await apiClient.post<NotificationTestResponse>(`/notifications/channels/${id}/test`, {});
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: notificationQueries.all() });
    },
  });
}

export function useCreateNotificationRuleMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: CreateNotificationRuleInput) => {
      const response = await apiClient.post<NotificationRule>('/notifications/rules', input);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: notificationQueries.all() });
    },
  });
}
