import { useState } from 'react';
import { useMutation } from 'react-relay';
import { toast } from 'sonner';
import { UpdateChatbotMutation } from '../graphql/UpdateChatbotMutation';
import type { UpdateChatbotMutation as UpdateChatbotMutationType } from '../graphql/__generated__/UpdateChatbotMutation.graphql';

const MODEL_OPTIONS = [
  { id: 1, name: 'gpt-4o', provider: 'OpenAI' },
  { id: 2, name: 'gpt-4o-mini', provider: 'OpenAI' },
  { id: 3, name: 'claude-3.5-sonnet', provider: 'Anthropic' },
];

interface ChatbotSettingsBasicProps {
  chatbot: {
    chatbotId: number;
    chatbotTitle: string;
    description: string | null | undefined;
    modelId: number | null | undefined;
  };
  onRefresh: () => void;
}

export function ChatbotSettingsBasic({ chatbot, onRefresh }: ChatbotSettingsBasicProps) {
  const [title, setTitle] = useState(chatbot.chatbotTitle);
  const [description, setDescription] = useState(chatbot.description ?? '');
  const [modelId, setModelId] = useState<number | null>(chatbot.modelId ?? null);
  const [titleError, setTitleError] = useState('');

  const [commitMutation, isInFlight] = useMutation<UpdateChatbotMutationType>(UpdateChatbotMutation);

  const handleSave = () => {
    if (!title.trim()) {
      setTitleError('제목을 입력해주세요');
      return;
    }

    commitMutation({
      variables: {
        input: {
          chatbotId: chatbot.chatbotId,
          chatbotPatch: {
            chatbotTitle: title.trim(),
            description: description.trim() || null,
            modelId: modelId,
          },
        },
      },
      onCompleted: () => {
        toast.success('설정이 저장되었습니다');
        onRefresh();
      },
      onError: (error) => {
        toast.error(`저장 실패: ${error.message}`);
      },
    });
  };

  return (
    <div className="space-y-5">
      {/* Title */}
      <div>
        <label htmlFor="settings-title" className="block text-sm font-medium text-foreground mb-1">
          제목 <span className="text-destructive">*</span>
        </label>
        <input
          id="settings-title"
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

      {/* Description */}
      <div>
        <label htmlFor="settings-description" className="block text-sm font-medium text-foreground mb-1">
          설명
        </label>
        <textarea
          id="settings-description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="챗봇에 대한 설명을 입력하세요"
          rows={3}
          className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 resize-none"
        />
      </div>

      {/* Model */}
      <div>
        <label htmlFor="settings-model" className="block text-sm font-medium text-foreground mb-1">
          모델
        </label>
        <select
          id="settings-model"
          value={modelId ?? ''}
          onChange={(e) => setModelId(e.target.value ? parseInt(e.target.value, 10) : null)}
          className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
        >
          <option value="">모델을 선택하세요</option>
          {MODEL_OPTIONS.map((model) => (
            <option key={model.id} value={model.id}>
              {model.name} ({model.provider})
            </option>
          ))}
        </select>
      </div>

      {/* Save Button */}
      <div className="flex justify-end pt-2">
        <button
          onClick={handleSave}
          disabled={isInFlight}
          className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isInFlight ? '저장 중...' : '저장'}
        </button>
      </div>
    </div>
  );
}
