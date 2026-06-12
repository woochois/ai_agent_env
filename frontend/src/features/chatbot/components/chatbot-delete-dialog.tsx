import { useMutation } from 'react-relay';
import { toast } from 'sonner';
import { DeleteChatbotMutation } from '../graphql/DeleteChatbotMutation';
import type { DeleteChatbotMutation as DeleteChatbotMutationType } from '../graphql/__generated__/DeleteChatbotMutation.graphql';

interface ChatbotDeleteDialogProps {
  open: boolean;
  onClose: () => void;
  chatbotId: number;
  chatbotTitle: string;
  onSuccess?: () => void;
}

export function ChatbotDeleteDialog({ open, onClose, chatbotId, chatbotTitle, onSuccess }: ChatbotDeleteDialogProps) {
  const [commitMutation, isInFlight] = useMutation<DeleteChatbotMutationType>(DeleteChatbotMutation);

  const handleDelete = () => {
    commitMutation({
      variables: {
        input: {
          chatbotId,
        },
      },
      onCompleted: () => {
        toast.success(`"${chatbotTitle}" 챗봇이 삭제되었습니다`);
        onClose();
        onSuccess?.();
      },
      onError: (error) => {
        toast.error(`삭제 실패: ${error.message}`);
      },
    });
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="fixed inset-0 bg-black/50" onClick={onClose} />
      <div className="relative z-10 w-full max-w-md rounded-xl bg-card border border-border p-6 shadow-xl">
        <h2 className="text-lg font-semibold text-foreground mb-2">챗봇 삭제</h2>
        <p className="text-sm text-muted-foreground mb-6">
          정말 <span className="font-medium text-foreground">"{chatbotTitle}"</span>을(를) 삭제하시겠습니까?
          <br />
          삭제된 챗봇은 복구할 수 없습니다.
        </p>

        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-lg px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
          >
            취소
          </button>
          <button
            onClick={handleDelete}
            disabled={isInFlight}
            className="rounded-lg bg-destructive px-4 py-2 text-sm font-medium text-destructive-foreground hover:bg-destructive/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isInFlight ? '삭제 중...' : '삭제'}
          </button>
        </div>
      </div>
    </div>
  );
}
