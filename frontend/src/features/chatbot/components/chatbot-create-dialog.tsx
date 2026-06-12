import { useState } from 'react';
import { useMutation } from 'react-relay';
import { toast } from 'sonner';
import { useAuth } from '@/components/auth-provider';
import { CreateChatbotMutation } from '../graphql/CreateChatbotMutation';
import type { CreateChatbotMutation as CreateChatbotMutationType } from '../graphql/__generated__/CreateChatbotMutation.graphql';

interface ChatbotCreateDialogProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function ChatbotCreateDialog({ open, onClose, onSuccess }: ChatbotCreateDialogProps) {
  const { currentUserId } = useAuth();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [titleError, setTitleError] = useState('');

  const [commitMutation, isInFlight] = useMutation<CreateChatbotMutationType>(CreateChatbotMutation);

  const handleSubmit = () => {
    if (!title.trim()) {
      setTitleError('제목을 입력해주세요');
      return;
    }

    commitMutation({
      variables: {
        input: {
          chatbot: {
            chatbotTitle: title.trim(),
            description: description.trim() || undefined,
            userId: currentUserId!,
          },
        },
      },
      onCompleted: () => {
        toast.success('챗봇이 생성되었습니다');
        handleClose();
        onSuccess();
      },
      onError: (error) => {
        toast.error(`생성 실패: ${error.message}`);
      },
    });
  };

  const handleClose = () => {
    setTitle('');
    setDescription('');
    setTitleError('');
    onClose();
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="fixed inset-0 bg-black/50" onClick={handleClose} />
      <div className="relative z-10 w-full max-w-md rounded-xl bg-card border border-border p-6 shadow-xl">
        <h2 className="text-lg font-semibold text-foreground mb-4">플레이그라운드 생성</h2>

        <div className="space-y-4">
          <div>
            <label htmlFor="chatbot-title" className="block text-sm font-medium text-foreground mb-1">
              제목 <span className="text-destructive">*</span>
            </label>
            <input
              id="chatbot-title"
              type="text"
              value={title}
              onChange={(e) => {
                setTitle(e.target.value);
                if (titleError) setTitleError('');
              }}
              placeholder="챗봇 제목을 입력하세요"
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
            {titleError && (
              <p className="mt-1 text-xs text-destructive">{titleError}</p>
            )}
          </div>

          <div>
            <label htmlFor="chatbot-description" className="block text-sm font-medium text-foreground mb-1">
              설명
            </label>
            <textarea
              id="chatbot-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="챗봇에 대한 설명을 입력하세요 (선택)"
              rows={3}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 resize-none"
            />
          </div>
        </div>

        <div className="flex justify-end gap-2 mt-6">
          <button
            onClick={handleClose}
            className="rounded-lg px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
          >
            취소
          </button>
          <button
            onClick={handleSubmit}
            disabled={isInFlight}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isInFlight ? '생성 중...' : '생성'}
          </button>
        </div>
      </div>
    </div>
  );
}
