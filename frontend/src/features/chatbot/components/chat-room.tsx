import { Suspense, useState, useCallback } from 'react';
import { useLazyLoadQuery, useMutation } from 'react-relay';
import { toast } from 'sonner';
import { SessionMessagesQuery } from '../graphql/SessionMessagesQuery';
import { SendChatMutation } from '../graphql/SendChatMutation';
import { ChatRoomMessages } from './chat-room-messages';
import { ChatRoomInput } from './chat-room-input';
import { ChatRoomPending } from './chat-room-pending';
import type { SessionMessagesQuery as SessionMessagesQueryType } from '../graphql/__generated__/SessionMessagesQuery.graphql';
import type { SendChatMutation as SendChatMutationType } from '../graphql/__generated__/SendChatMutation.graphql';

interface ChatRoomProps {
  sessionId: string;
  chatbotId: number;
}

export function ChatRoom({ sessionId, chatbotId }: ChatRoomProps) {
  return (
    <Suspense
      fallback={
        <div className="flex-1 flex items-center justify-center text-muted-foreground">
          메시지를 불러오는 중...
        </div>
      }
    >
      <ChatRoomContent sessionId={sessionId} chatbotId={chatbotId} />
    </Suspense>
  );
}

function ChatRoomContent({ sessionId, chatbotId }: ChatRoomProps) {
  const [isSending, setIsSending] = useState(false);
  const [fetchKey, setFetchKey] = useState(0);

  const data = useLazyLoadQuery<SessionMessagesQueryType>(
    SessionMessagesQuery,
    { sessionId },
    { fetchKey, fetchPolicy: 'store-and-network' }
  );

  const [commitSendChat] = useMutation<SendChatMutationType>(SendChatMutation);

  const messages = data.chatbotSessionBySessionId?.chatbotMessagesBySessionId?.nodes ?? [];

  const handleSend = useCallback(
    (message: string) => {
      setIsSending(true);

      commitSendChat({
        variables: {
          input: {
            chatbotId,
            sessionId,
            message,
          },
        },
        onCompleted: () => {
          setIsSending(false);
          // Refetch messages to show the new ones
          setFetchKey((k) => k + 1);
        },
        onError: (error) => {
          setIsSending(false);
          toast.error(`전송 실패: ${error.message}`);
        },
      });
    },
    [chatbotId, sessionId, commitSendChat]
  );

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <ChatRoomMessages messages={messages} />
      <ChatRoomPending visible={isSending} />
      <ChatRoomInput onSend={handleSend} disabled={isSending} />
    </div>
  );
}
