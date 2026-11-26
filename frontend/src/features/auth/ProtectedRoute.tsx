import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { getDefaultRouteForRole, useAuth } from "@/features/auth/AuthContext";
import type { UserRole } from "@/services/api";

interface ProtectedRouteProps {
  allowedRoles: UserRole[];
  children: ReactNode;
}

export function ProtectedRoute({ allowedRoles, children }: ProtectedRouteProps) {
  const { user, isBootstrapping } = useAuth();

  if (isBootstrapping) {
    return <LoadingSkeleton rows={3} />;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (!allowedRoles.includes(user.role)) {
    return <Navigate to={getDefaultRouteForRole(user.role)} replace />;
  }

  return <>{children}</>;
}

