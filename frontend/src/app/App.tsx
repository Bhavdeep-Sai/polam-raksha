import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { AppShell } from "@/components/layout/AppShell";
import { AuthProvider } from "@/features/auth/AuthContext";
import { LoginPage } from "@/features/auth/LoginPage";
import { ProtectedRoute } from "@/features/auth/ProtectedRoute";
import { RegisterPage } from "@/features/auth/RegisterPage";
import { LandingPage } from "@/features/public/LandingPage";
import { SystemStatusPage } from "@/features/system/SystemStatusPage";

const FarmerDashboard = lazy(() =>
  import("@/features/farmers/FarmerDashboard").then((m) => ({ default: m.FarmerDashboard })),
);
const BuyerDashboard = lazy(() =>
  import("@/features/buyers/BuyerDashboard").then((m) => ({ default: m.BuyerDashboard })),
);
const OperatorDashboard = lazy(() =>
  import("@/features/operators/OperatorDashboard").then((m) => ({
    default: m.OperatorDashboard,
  })),
);
const AdminDashboard = lazy(() =>
  import("@/features/admin/AdminDashboard").then((m) => ({ default: m.AdminDashboard })),
);
const IvrSimulatorPage = lazy(() =>
  import("@/features/ivr/IvrSimulatorPage").then((m) => ({ default: m.IvrSimulatorPage })),
);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  },
});

export function AppRoutes() {
  return (
    <AppShell>
      <Suspense fallback={<LoadingSkeleton rows={4} />}>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/system" element={<SystemStatusPage />} />
          <Route path="/ivr" element={<IvrSimulatorPage />} />

          <Route
            path="/farmer/*"
            element={
              <ProtectedRoute allowedRoles={["FARMER"]}>
                <FarmerDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/buyer/*"
            element={
              <ProtectedRoute allowedRoles={["BUYER"]}>
                <BuyerDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/operator/*"
            element={
              <ProtectedRoute allowedRoles={["OPERATOR"]}>
                <OperatorDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/*"
            element={
              <ProtectedRoute allowedRoles={["ADMIN"]}>
                <AdminDashboard />
              </ProtectedRoute>
            }
          />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </AppShell>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
