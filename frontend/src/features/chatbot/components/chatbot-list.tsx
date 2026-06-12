import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { MessageSquare, Trash2 } from 'lucide-react';
import { ChatbotDeleteDialog } from './chatbot-delete-dialog';

interface ChatbotNode {
  readonly id: string;
  readonly chatbotId: number;
  readonly chatbotTitle: string;
  readonly description: string | null | undefined;
  readonly createdAt: any | null | undefined;
}

interface ChatbotListProps {
  chatbots: ReadonlyArray<ChatbotNode>;
  onRefresh?: () => void;
}

export function ChatbotList({ chatbots, onRefresh }: ChatbotListProps) {
  const navigate = useNavigate();
  const [deleteTarget, setDeleteTarget] = useState<{ chatbotId: number; title: string } | null>(null);

  if (chatbots.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
        <MessageSquare className="h-12 w-12 mb-4 opacity-50" />
        <p className="text-lg font-medium">플레이그라운드를 추가해보세요</p>
        <p className="text-sm mt-1">상단의 '플레이그라운드 추가' 버튼을 클릭하세요</p>
      </div>
    );
  }

  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {chatbots.map((chatbot) => (
          <div
            key={chatbot.id}
            onClick={() => navigate(`/chatbot/${chatbot.chatbotId}`)}
            className="group cursor-pointer rounded-xl border border-border bg-card p-5 transition-all hover:border-primary/50 hover:shadow-md"
          >
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <MessageSquare className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="font-semibold text-foreground group-hover:text-primary transition-colors truncate">
                  {chatbot.chatbotTitle}
                </h3>
                {chatbot.description && (
                  <p className="mt-1 text-sm text-muted-foreground line-clamp-2">
                    {chatbot.description}
                  </p>
                )}
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setDeleteTarget({ chatbotId: chatbot.chatbotId, title: chatbot.chatbotTitle });
                }}
                className="shrink-0 rounded-lg p-1.5 text-muted-foreground opacity-0 group-hover:opacity-100 hover:bg-destructive/10 hover:text-destructive transition-all"
                aria-label={`${chatbot.chatbotTitle} 삭제`}
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          </div>
        ))}
      </div>

      {deleteTarget && (
        <ChatbotDeleteDialog
          open={true}
          onClose={() => setDeleteTarget(null)}
          chatbotId={deleteTarget.chatbotId}
          chatbotTitle={deleteTarget.title}
          onSuccess={onRefresh}
        />
      )}
    </>
  );
}
