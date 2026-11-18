import { ReadReply } from "../features/chat/Voice";
import { usePreferences } from "../hooks/usePreferences";
/** Speak the actual parent record using the shared local controller; no duplicate record fetch. */
export function AudioPlayer({ text }: { text: string }) {
  const { preferences } = usePreferences();
  return (
    <ReadReply
      text={text}
      volume={preferences.playbackVolume}
      speakerId={preferences.speakerId}
    />
  );
}
