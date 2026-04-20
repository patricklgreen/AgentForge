import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderOptions } from "@testing-library/react";

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

type ProviderOpts = {
  client?: QueryClient;
};

export function renderWithProviders(
  ui: React.ReactElement,
  { client = createTestQueryClient(), ...options }: ProviderOpts & Omit<RenderOptions, "wrapper"> = {}
) {
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { ...render(ui, { wrapper: Wrapper, ...options }), queryClient: client };
}
