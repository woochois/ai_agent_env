import { useEffect, useRef } from 'react';
import { ChatMarkdown } from '@/components/chat-markdown';

interface Message {
  readonly id: string;
  readonly messageId: number;
  readonly role: string;
  readonly content: string;
  readonly toolCalls: ReadonlyArray<string | null | undefined> | null | undefined;
  readonly sources: ReadonlyArray<string | null | undefined> | null | undefined;
  readonly elapsedMs: number | null | undefined;
  readonly createdAt: any | null | undefined;
}

interface ChatRoomMessagesProps {
  messages: ReadonlyArray<Message>;
}

export function ChatRoomMessages({ messages }: ChatRoomMessagesProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground p-8">
        <p className="text-lg font-medium">대화를 시작해보세요</p>
        <p className="text-sm mt-1">메시지를 입력하면 AI가 응답합니다</p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
      <div ref={messagesEndRef} />
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user';

  if (isUser) {
    return (
      <div className="flex justify-end items-start gap-2">
        <div className="max-w-[70%] rounded-2xl bg-teal-600 text-white px-4 py-2.5 shadow-sm">
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        </div>
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-teal-100 dark:bg-teal-900 flex items-center justify-center text-sm">
          👤
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start items-start gap-2">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-muted flex items-center justify-center text-sm">
        🤖
      </div>
      <div className="max-w-[70%] space-y-1">
        <div className="rounded-2xl bg-muted px-4 py-2.5 shadow-sm">
          <ChatMarkdown content={message.content} className="text-sm" />
        </div>
        {message.elapsedMs != null && message.elapsedMs > 0 && (
          <p className="text-xs text-muted-foreground pl-2">
            {(message.elapsedMs / 1000).toFixed(2)}초 동안 생각함
          </p>
        )}
        {message.toolCalls && message.toolCalls.length > 0 && (
          <ChatRoomToolsInline toolCalls={message.toolCalls} />
        )}
        {message.sources && message.sources.length > 0 && (
          <ChatRoomSourcesInline sources={message.sources} />
        )}
      </div>
    </div>
  );
}

function ChatRoomToolsInline({ toolCalls }: { toolCalls: ReadonlyArray<string | null | undefined> }) {
  const validTools = toolCalls.filter((t): t is string => !!t);
  if (validTools.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1.5 pl-2 pt-1">
      {validTools.map((tool, idx) => (
        <span
          key={idx}
          className="inline-flex items-center gap-1 rounded-full bg-blue-100 dark:bg-blue-900/30 px-2.5 py-0.5 text-xs text-blue-700 dark:text-blue-300"
        >
          🔧 {tool}
        </span>
      ))}
    </div>
  );
}

function ChatRoomSourcesInline({ sources }: { sources: ReadonlyArray<string | null | undefined> }) {
  const validSources = sources.filter((s): s is string => !!s);
  if (validSources.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1.5 pl-2 pt-1">
      {validSources.map((source, idx) => (
        <span
          key={idx}
          className="inline-flex items-center gap-1 rounded-md border border-border bg-card px-2.5 py-1 text-xs text-muted-foreground shadow-sm"
        >
          📄 {source}
        </span>
      ))}
    </div>
  );
}
