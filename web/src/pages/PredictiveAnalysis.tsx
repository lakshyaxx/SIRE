import { useNavigate } from "react-router";
import { Predictions } from "../features/predictions/Predictions";
/** Preserve real dataset/model inventory, compatible CSV validation and source-matched comparisons. */
export function PredictiveAnalysis() {
  const navigate = useNavigate();
  return (
    <div className="integrated-feature prediction-center">
      <Predictions
        discuss={(id) => navigate(`/chat?prediction=${encodeURIComponent(id)}`)}
      />
    </div>
  );
}
