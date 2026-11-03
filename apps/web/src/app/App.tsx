// Root providers: query cache, staff auth, and router.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { useEffect } from "react";

import { AuthProvider, useAuth } from "@/features/auth/AuthProvider";
import { router } from "./router";

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 60_000, refetchOnWindowFocus: false } } });

// Re-run the route guards whenever the session changes (loaded, signed in, signed out).
function Routes() {
  const auth = useAuth();
  useEffect(() => {
    void router.invalidate();
  }, [auth.loading, auth.client]);
  return <RouterProvider router={router} context={{ auth }} />;
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <Routes />
      </AuthProvider>
    </QueryClientProvider>
  );
}
