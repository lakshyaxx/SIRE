import { RouterProvider } from "react-router";
import { ApiProvider } from "@/hooks/useApi";
import { PreferencesProvider } from "@/hooks/usePreferences";
import { router } from "./routes";

export default function App() {
  return (
    <PreferencesProvider>
      <ApiProvider>
        <RouterProvider router={router} />
      </ApiProvider>
    </PreferencesProvider>
  );
}
