import { TypingIndicator } from '@/components/typing-indicator';

interface ChatRoomPendingProps {
  visible: boolean;
}

export function ChatRoomPending({ visible }: ChatRoomPendingProps) {
  if (!visible) return null;

  return (
    <div className="flex items-start gap-2 px-4 pb-2">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-muted flex items-center justify-center text-sm">
        🤖
      </div>
      <div className="rounded-2xl bg-muted px-4 py-2.5 shadow-sm">
        <TypingIndicator />
      </div>
    </div>
  );
}
