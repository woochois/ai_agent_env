import { Suspense, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useLazyLoadQuery, useMutation } from 'react-relay';
import { toast } from 'sonner';
import { Settings } from 'lucide-react';
import { ChatbotDetailQuery } from '../graphql/ChatbotDetailQuery';
import { CreateSessionMutation } from '../graphql/CreateSessionMutation';
import { ChatbotSessionList } from '../components/chatbot-session-list';
import { ChatRoom } from '../components/chat-room';
import { ChatbotSettings } from '../components/chatbot-settings';
import type { ChatbotDetailQuery as ChatbotDetailQueryType } from '../graphql/__generated__/ChatbotDetailQuery.graphql';
import type { CreateSessionMutation as CreateSessionMutationType } from '../graphql/__generated__/CreateSessionMutation.graphql';

export function ChatbotDetailPage() {
  return (
    <Suspense
      fallback={<div className="flex items-center justify-center h-full text-muted-foreground">로딩 중...</div>}
    >
      <ChatbotDetailContent />
    </Suspense>
  );
}

function ChatbotDetailContent() {
  const { id } = useParams<{ id: string }>();
  const chatbotId = parseInt(id!, 10);

  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [fetchKey, setFetchKey] = useState(0);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const data = useLazyLoadQuery<ChatbotDetailQueryType>(ChatbotDetailQuery, { chatbotId }, { fetchKey });
  const chatbot = data.chatbotByChatbotId;

  const [commitCreateSession] = useMutation<CreateSessionMutationType>(CreateSessionMutation);

  if (!chatbot) {
    return <div className="flex items-center justify-center h-full text-muted-foreground">챗봇을 찾을 수 없습니다</div>;
  }

  const sessions = chatbot.chatbotSessionsByChatbotId?.nodes ?? [];

  const handleNewChat = () => {
    commitCreateSession({
      variables: {
        input: {
          chatbotSession: {
            chatbotId,
            title: '새 채팅',
            userId: 1, // TODO: get from auth context
          },
        },
      },
      onCompleted: (response) => {
        const newSession = response.createChatbotSession?.chatbotSession;
        if (newSession) {
          toast.success('새 채팅이 생성되었습니다');
          setSelectedSessionId(newSession.sessionId);
          setFetchKey((k) => k + 1);
        }
      },
      onError: (error) => {
        toast.error(`생성 실패: ${error.message}`);
      },
    });
  };

  const handleRefresh = () => {
    setFetchKey((k) => k + 1);
  };

  return (
    <div className="flex h-full overflow-hidden">
      {/* Session Sidebar */}
      <ChatbotSessionList
        chatbotId={chatbotId}
        chatbotTitle={chatbot.chatbotTitle}
        sessions={sessions}
        selectedSessionId={selectedSessionId}
        onSelectSession={setSelectedSessionId}
        onNewChat={handleNewChat}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed((c) => !c)}
        onRefresh={handleRefresh}
      />

      {/* Chat Area */}
      <div className="flex-1 flex flex-col overflow-hidden relative">
        {/* Settings Button */}
        <div className="absolute top-2 right-2 z-10">
          <button
            onClick={() => setSettingsOpen(true)}
            className="rounded-lg p-2 text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
            aria-label="챗봇 설정"
          >
            <Settings className="h-5 w-5" />
          </button>
        </div>

        {selectedSessionId ? (
          <ChatRoom sessionId={selectedSessionId} chatbotId={chatbotId} />
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground">
            <p className="text-lg font-medium">새 대화를 시작해보세요</p>
            <p className="text-sm mt-1">좌측에서 세션을 선택하거나 새 채팅을 만드세요</p>
          </div>
        )}
      </div>

      {/* Settings Dialog */}
      <ChatbotSettings
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        chatbot={chatbot}
        onRefresh={handleRefresh}
      />
    </div>
  );
}
