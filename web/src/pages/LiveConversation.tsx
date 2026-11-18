import { Assistant } from "./Assistant";
/** The same conversation pipeline with persistent microphone transport and automatic reply audio. */
export function LiveConversation() {
  return <Assistant live />;
}
