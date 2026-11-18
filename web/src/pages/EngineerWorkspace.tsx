import { useNavigate } from "react-router";
import { Engineer } from "../features/engineer/Engineer";
/** Preserved scenario replay, source-scoped prior cases, fleet and explicit what-if operations. */
export function EngineerWorkspace() {
  const navigate = useNavigate();
  return (
    <div className="integrated-feature">
      <Engineer navigate={navigate} />
    </div>
  );
}
