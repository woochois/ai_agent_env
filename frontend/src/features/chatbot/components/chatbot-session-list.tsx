import { useState } from 'react';
import { useMutation } from 'react-relay';
import { toast } from 'sonner';
import { Plus, Trash2, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { cn } from '@/lib/utils';
import { DeleteSessionMutation } from '../graphql/DeleteSessionMutation';
import type { DeleteSessionMutation as DeleteSessionMutationType } from '../graphql/__generated__/DeleteSessionMutation.graphql';

interface SessionItem {
  readonly id: string;
  readonly sessionId: string;
  readonly title: string;
  readonly createdAt: any;
}

interface ChatbotSessionListProps {
  chatbotId: number;
  chatbotTitle: string;
  sessions: ReadonlyArray<SessionItem>;
  selectedSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
  onRefresh: () => void;
}

export function ChatbotSessionList({
  chatbotTitle,
  sessions,
  selectedSessionId,
  onSelectSession,
  onNewChat,
  collapsed,
  onToggleCollapse,
  onRefresh,
}: ChatbotSessionListProps) {
  const [hoveredSessionId, setHoveredSessionId] = useState<string | null>(null);
  const [commitDelete, isDeleting] = useMutation<DeleteSessionMutationType>(DeleteSessionMutation);

  const handleDeleteSession = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    commitDelete({
      variables: {
        input: { sessionId },
      },
      onCompleted: () => {
        toast.success('세션이 삭제되었습니다');
        onRefresh();
      },
      onError: (error) => {
        toast.error(`삭제 실패: ${error.message}`);
      },
    });
  };

  // Collapsed state: show only expand button
  if (collapsed) {
    return (
      <button
        onClick={onToggleCollapse}
        className="absolute left-0 top-4 z-10 rounded-r-lg border border-l-0 border-border bg-card px-2 py-2 text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
        title="펼치기"
      >
        <PanelLeftOpen className="h-4 w-4" />
      </button>
    );
  }

  return (
    <div className="w-60 border-r border-border flex flex-col bg-card shrink-0">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <span className="text-sm font-semibold text-foreground truncate" title={chatbotTitle}>
          {chatbotTitle}
        </span>
        <button
          onClick={onToggleCollapse}
          className="text-muted-foreground hover:text-foreground transition-colors"
          title="접기"
        >
          <PanelLeftClose className="h-4 w-4" />
        </button>
      </div>

      {/* New Chat Button */}
      <div className="px-3 py-2 border-b border-border">
        <button
          onClick={onNewChat}
          className="flex items-center gap-2 w-full rounded-lg px-3 py-2 text-sm font-medium text-primary hover:bg-primary/10 transition-colors"
        >
          <Plus className="h-4 w-4" />
          새 채팅
        </button>
      </div>

      {/* Session List */}
      <div className="flex-1 overflow-auto p-2 space-y-1">
        {sessions.length === 0 ? (
          <p className="text-xs text-muted-foreground text-center py-4">
            세션이 없습니다
          </p>
        ) : (
          sessions.map((session) => (
            <div
              key={session.sessionId}
              onClick={() => onSelectSession(session.sessionId)}
              onMouseEnter={() => setHoveredSessionId(session.sessionId)}
              onMouseLeave={() => setHoveredSessionId(null)}
              className={cn(
                'group cursor-pointer rounded-lg px-3 py-2 text-sm transition-colors relative flex items-center',
                selectedSessionId === session.sessionId
                  ? 'bg-primary/10 text-primary border border-primary/30'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
              )}
            >
              <span className="truncate flex-1">{session.title}</span>
              {hoveredSessionId === session.sessionId && (
                <button
                  onClick={(e) => handleDeleteSession(e, session.sessionId)}
                  disabled={isDeleting}
                  className="shrink-0 ml-1 p-1 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
                  title="세션 삭제"
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
