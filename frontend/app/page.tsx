import { Suspense } from "react";
import { DashboardWorkspace } from "../components/dashboard/dashboard-workspace";

export default function HomePage() {
  return (
    <Suspense>
      <DashboardWorkspace />
    </Suspense>
  );
}
