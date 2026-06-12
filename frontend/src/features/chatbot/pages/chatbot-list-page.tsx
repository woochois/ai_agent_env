import { Suspense, useState, useCallback } from 'react';
import { useLazyLoadQuery } from 'react-relay';
import { PageLayout } from '@/components/page-layout';
import { useAuth } from '@/components/auth-provider';
import { ChatbotList } from '../components/chatbot-list';
import { ChatbotCreateDialog } from '../components/chatbot-create-dialog';
import { ChatbotListQuery } from '../graphql/ChatbotListQuery';
import type { ChatbotListQuery as ChatbotListQueryType } from '../graphql/__generated__/ChatbotListQuery.graphql';
import { Plus } from 'lucide-react';

export function ChatbotListPage() {
  return (
    <Suspense
      fallback={
        <PageLayout title="플레이그라운드" description="AI 챗봇을 만들고 대화해보세요">
          <div className="flex items-center justify-center py-20 text-muted-foreground">
            로딩 중...
          </div>
        </PageLayout>
      }
    >
      <ChatbotListContent />
    </Suspense>
  );
}

function ChatbotListContent() {
  const { currentUserId } = useAuth();
  const [showCreate, setShowCreate] = useState(false);
  const [fetchKey, setFetchKey] = useState(0);

  const data = useLazyLoadQuery<ChatbotListQueryType>(ChatbotListQuery, {
    userId: currentUserId!,
    isDeleted: { equalTo: false },
  }, { fetchKey });

  const chatbots = data.allChatbots?.nodes ?? [];

  const handleRefresh = useCallback(() => {
    setFetchKey((prev) => prev + 1);
  }, []);

  return (
    <PageLayout
      title="플레이그라운드"
      description="AI 챗봇을 만들고 대화해보세요"
      action={
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          <Plus className="h-4 w-4" />
          플레이그라운드 추가
        </button>
      }
    >
      <ChatbotList chatbots={chatbots} onRefresh={handleRefresh} />
      <ChatbotCreateDialog
        open={showCreate}
        onClose={() => setShowCreate(false)}
        onSuccess={handleRefresh}
      />
    </PageLayout>
  );
}
