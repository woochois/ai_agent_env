import { useState } from 'react';
import { useMutation } from 'react-relay';
import { toast } from 'sonner';
import { Plus, Trash2 } from 'lucide-react';
import { CreateGuardRulesetMutation } from '../graphql/CreateGuardRulesetMutation';
import { DeleteGuardRulesetMutation } from '../graphql/DeleteGuardRulesetMutation';
import type { CreateGuardRulesetMutation as CreateGuardRulesetMutationType } from '../graphql/__generated__/CreateGuardRulesetMutation.graphql';
import type { DeleteGuardRulesetMutation as DeleteGuardRulesetMutationType } from '../graphql/__generated__/DeleteGuardRulesetMutation.graphql';

interface ChatbotSettingsGuardProps {
  chatbot: {
    chatbotId: number;
    guardRulesetsByChatbotId: {
      nodes: ReadonlyArray<{
        id: string;
        guardRulesetId: number;
        rule: string;
        orderIndex: number;
      }>;
    };
  };
  onRefresh: () => void;
}

export function ChatbotSettingsGuard({ chatbot, onRefresh }: ChatbotSettingsGuardProps) {
  const [newRule, setNewRule] = useState('');

  const [commitCreate, isCreating] = useMutation<CreateGuardRulesetMutationType>(CreateGuardRulesetMutation);
  const [commitDelete] = useMutation<DeleteGuardRulesetMutationType>(DeleteGuardRulesetMutation);

  const rules = chatbot.guardRulesetsByChatbotId.nodes;

  const handleAdd = () => {
    const ruleText = newRule.trim();
    if (!ruleText) return;

    const nextOrderIndex = rules.length > 0
      ? Math.max(...rules.map((r) => r.orderIndex)) + 1
      : 0;

    commitCreate({
      variables: {
        input: {
          guardRuleset: {
            chatbotId: chatbot.chatbotId,
            rule: ruleText,
            orderIndex: nextOrderIndex,
          },
        },
      },
      onCompleted: () => {
        toast.success('규칙이 추가되었습니다');
        setNewRule('');
        onRefresh();
      },
      onError: (error) => {
        toast.error(`추가 실패: ${error.message}`);
      },
    });
  };

  const handleDelete = (guardRulesetId: number) => {
    commitDelete({
      variables: {
        input: {
          guardRulesetId,
        },
      },
      onCompleted: () => {
        toast.success('규칙이 삭제되었습니다');
        onRefresh();
      },
      onError: (error) => {
        toast.error(`삭제 실패: ${error.message}`);
      },
    });
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleAdd();
    }
  };

  return (
    <div className="space-y-5">
      {/* Add Rule Input */}
      <div>
        <label htmlFor="guard-rule-input" className="block text-sm font-medium text-foreground mb-1">
          새 규칙 추가
        </label>
        <div className="flex gap-2">
          <input
            id="guard-rule-input"
            type="text"
            value={newRule}
            onChange={(e) => setNewRule(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="예: 개인정보를 요청하지 마세요"
            className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
          />
          <button
            onClick={handleAdd}
            disabled={isCreating || !newRule.trim()}
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Plus className="h-4 w-4" />
            추가
          </button>
        </div>
      </div>

      {/* Rules List */}
      <div>
        <h3 className="text-sm font-medium text-foreground mb-2">
          등록된 규칙 ({rules.length})
        </h3>
        {rules.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border p-6 text-center">
            <p className="text-sm text-muted-foreground">
              규칙을 추가하면 AI의 응답 범위를 제한할 수 있습니다
            </p>
          </div>
        ) : (
          <ul className="space-y-2">
            {rules.map((rule) => (
              <li
                key={rule.guardRulesetId}
                className="flex items-center justify-between rounded-lg border border-border bg-background px-3 py-2.5 group"
              >
                <span className="text-sm text-foreground">{rule.rule}</span>
                <button
                  onClick={() => handleDelete(rule.guardRulesetId)}
                  className="rounded p-1 text-muted-foreground hover:text-destructive hover:bg-destructive/10 opacity-0 group-hover:opacity-100 transition-all"
                  aria-label={`규칙 삭제: ${rule.rule}`}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
