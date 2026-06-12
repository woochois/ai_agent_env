import { useState } from 'react';
import { Settings, X } from 'lucide-react';
import { ChatbotSettingsBasic } from './chatbot-settings-basic';
import { ChatbotSettingsPrompt } from './chatbot-settings-prompt';
import { ChatbotSettingsGuard } from './chatbot-settings-guard';
import { ChatbotSettingsTool } from './chatbot-settings-tool';

type TabKey = 'basic' | 'prompt' | 'guard' | 'tool';

const TABS: { key: TabKey; label: string }[] = [
  { key: 'basic', label: '기본 설정' },
  { key: 'prompt', label: '프롬프트' },
  { key: 'guard', label: '가드레일' },
  { key: 'tool', label: '도구' },
];

interface ChatbotSettingsProps {
  open: boolean;
  onClose: () => void;
  chatbot: {
    chatbotId: number;
    chatbotTitle: string;
    description: string | null | undefined;
    chatbotPrompt: string | null | undefined;
    modelId: number | null | undefined;
    guardRulesetsByChatbotId: {
      nodes: ReadonlyArray<{
        id: string;
        guardRulesetId: number;
        rule: string;
        orderIndex: number;
      }>;
    };
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

export function ChatbotSettings({ open, onClose, chatbot, onRefresh }: ChatbotSettingsProps) {
  const [activeTab, setActiveTab] = useState<TabKey>('basic');

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="fixed inset-0 bg-black/50" onClick={onClose} />
      <div className="relative z-10 w-full max-w-2xl max-h-[80vh] rounded-xl bg-card border border-border shadow-xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div className="flex items-center gap-2">
            <Settings className="h-5 w-5 text-muted-foreground" />
            <h2 className="text-lg font-semibold text-foreground">챗봇 설정</h2>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
            aria-label="닫기"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-border px-6">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-2.5 text-sm font-medium transition-colors relative ${
                activeTab === tab.key
                  ? 'text-primary'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              {tab.label}
              {activeTab === tab.key && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary rounded-full" />
              )}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {activeTab === 'basic' && (
            <ChatbotSettingsBasic chatbot={chatbot} onRefresh={onRefresh} />
          )}
          {activeTab === 'prompt' && (
            <ChatbotSettingsPrompt chatbot={chatbot} onRefresh={onRefresh} />
          )}
          {activeTab === 'guard' && (
            <ChatbotSettingsGuard chatbot={chatbot} onRefresh={onRefresh} />
          )}
          {activeTab === 'tool' && (
            <ChatbotSettingsTool chatbot={chatbot} onRefresh={onRefresh} />
          )}
        </div>
      </div>
    </div>
  );
}
