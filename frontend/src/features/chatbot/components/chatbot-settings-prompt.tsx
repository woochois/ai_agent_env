import { useState } from 'react';
import { useMutation } from 'react-relay';
import { toast } from 'sonner';
import { UpdateChatbotMutation } from '../graphql/UpdateChatbotMutation';
import type { UpdateChatbotMutation as UpdateChatbotMutationType } from '../graphql/__generated__/UpdateChatbotMutation.graphql';

interface ChatbotSettingsPromptProps {
  chatbot: {
    chatbotId: number;
    chatbotPrompt: string | null | undefined;
  };
  onRefresh: () => void;
}

export function ChatbotSettingsPrompt({ chatbot, onRefresh }: ChatbotSettingsPromptProps) {
  const [prompt, setPrompt] = useState(chatbot.chatbotPrompt ?? '');

  const [commitMutation, isInFlight] = useMutation<UpdateChatbotMutationType>(UpdateChatbotMutation);

  const handleSave = () => {
    commitMutation({
      variables: {
        input: {
          chatbotId: chatbot.chatbotId,
          chatbotPatch: {
            chatbotPrompt: prompt.trim() || null,
          },
        },
      },
      onCompleted: () => {
        toast.success('프롬프트가 저장되었습니다');
        onRefresh();
      },
      onError: (error) => {
        toast.error(`저장 실패: ${error.message}`);
      },
    });
  };

  return (
    <div className="space-y-5">
      <div>
        <label htmlFor="settings-prompt" className="block text-sm font-medium text-foreground mb-1">
          시스템 프롬프트
        </label>
        <textarea
          id="settings-prompt"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="AI의 역할과 행동 방식을 정의하는 시스템 프롬프트를 입력하세요. 예: '당신은 친절한 고객 서비스 도우미입니다.'"
          rows={12}
          className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 resize-none font-mono"
        />
        <p className="mt-1 text-xs text-muted-foreground">
          시스템 프롬프트는 AI의 응답 스타일과 역할을 정의합니다.
        </p>
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
