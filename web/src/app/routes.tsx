import { createBrowserRouter, Navigate } from "react-router";
import { AppShell } from "@/components/AppShell";
import { Assistant } from "@/pages/Assistant";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: AppShell,
    children: [
      { index: true, Component: Assistant },
      { path: "chat", Component: Assistant },
      { path: "chat/:id", Component: Assistant },
      {
        path: "live/:id?",
        lazy: async () => ({
          Component: (await import("@/pages/LiveConversation"))
            .LiveConversation,
        }),
      },
      {
        path: "investigations/new",
        lazy: async () => ({
          Component: (await import("@/pages/NewInvestigation"))
            .NewInvestigation,
        }),
      },
      {
        path: "investigations/:id",
        lazy: async () => ({
          Component: (await import("@/pages/InvestigationWorkspace"))
            .InvestigationWorkspace,
        }),
      },
      {
        path: "evidence",
        lazy: async () => ({
          Component: (await import("@/pages/DataEvidence")).DataEvidence,
        }),
      },
      {
        path: "rul",
        lazy: async () => ({
          Component: (await import("@/pages/PredictiveAnalysis"))
            .PredictiveAnalysis,
        }),
      },
      {
        path: "cases",
        lazy: async () => ({
          Component: (await import("@/pages/Investigations")).Investigations,
        }),
      },
      {
        path: "status",
        lazy: async () => ({
          Component: (await import("@/pages/SystemStatus")).SystemStatus,
        }),
      },
      {
        path: "settings",
        lazy: async () => ({
          Component: (await import("@/pages/Settings")).Settings,
        }),
      },
      { path: "overview", element: <Navigate replace to="/cases" /> },
      {
        path: "engineer",
        lazy: async () => ({
          Component: (await import("../pages/EngineerWorkspace"))
            .EngineerWorkspace,
        }),
      },
      {
        path: "models",
        lazy: async () => ({
          Component: (await import("../pages/Models")).ModelInventory,
        }),
      },
      {
        path: "knowledge",
        lazy: async () => ({
          Component: (await import("../pages/KnowledgeWorkspace"))
            .KnowledgeWorkspace,
        }),
      },
      { path: "predictions", element: <Navigate replace to="/rul" /> },
      { path: "assets", element: <Navigate replace to="/rul" /> },
      { path: "data", element: <Navigate replace to="/evidence" /> },
      { path: "predictive-analysis", element: <Navigate replace to="/rul" /> },
      { path: "investigations", element: <Navigate replace to="/cases" /> },
      {
        path: "*",
        lazy: async () => ({
          Component: (await import("@/pages/NotFound")).NotFound,
        }),
      },
    ],
  },
]);
