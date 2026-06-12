import { useMutation } from 'react-relay';
import { toast } from 'sonner';
import { UpdateToolAgentMutation } from '../graphql/UpdateToolAgentMutation';
import type { UpdateToolAgentMutation as UpdateToolAgentMutationType } from '../graphql/__generated__/UpdateToolAgentMutation.graphql';

interface ChatbotSettingsToolProps {
  chatbot: {
    chatbotToolAgentsByChatbotId: {
      nodes: ReadonlyArray<{
        id: string;
        chatbotToolAgentId: number;
        toolAgentKey: string;
        isEnabled: boolean;
      }>;
    };
  };
  onRefresh: () => void;
}

export function ChatbotSettingsTool({ chatbot, onRefresh }: ChatbotSettingsToolProps) {
  const [commitUpdate] = useMutation<UpdateToolAgentMutationType>(UpdateToolAgentMutation);

  const toolAgents = chatbot.chatbotToolAgentsByChatbotId.nodes;

  const handleToggle = (agentId: number, currentEnabled: boolean) => {
    commitUpdate({
      variables: {
        input: {
          id: agentId,
          chatbotToolAgentPatch: {
            isEnabled: !currentEnabled,
          },
        },
      },
      onCompleted: () => {
        toast.success('에이전트 설정이 변경되었습니다');
        onRefresh();
      },
      onError: (error) => {
        toast.error(`변경 실패: ${error.message}`);
      },
    });
  };

  if (toolAgents.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border p-6 text-center">
        <p className="text-sm text-muted-foreground">
          등록된 에이전트가 없습니다
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium text-foreground mb-2">
        도구 에이전트 ({toolAgents.length})
      </h3>
      <ul className="space-y-2">
        {toolAgents.map((agent) => (
          <li
            key={agent.chatbotToolAgentId}
            className="flex items-center justify-between rounded-lg border border-border bg-background px-4 py-3"
          >
            <div>
              <span className="text-sm font-medium text-foreground">
                {agent.toolAgentKey}
              </span>
            </div>
            <button
              role="switch"
              aria-checked={agent.isEnabled}
              aria-label={`${agent.toolAgentKey} 토글`}
              onClick={() => handleToggle(agent.chatbotToolAgentId, agent.isEnabled)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                agent.isEnabled ? 'bg-primary' : 'bg-muted'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 rounded-full bg-white transition-transform ${
                  agent.isEnabled ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
