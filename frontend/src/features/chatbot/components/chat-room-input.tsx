import { useRef, useState, useCallback } from 'react';
import { Send } from 'lucide-react';

interface ChatRoomInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
}

const MAX_CHARS = 5000;
const MAX_HEIGHT = 144;

export function ChatRoomInput({ onSend, disabled = false }: ChatRoomInputProps) {
  const [value, setValue] = useState('');
  const [isComposing, setIsComposing] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const adjustHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, MAX_HEIGHT)}px`;
  }, []);

  const handleSend = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue('');
    // Reset height after clearing
    requestAnimationFrame(() => {
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    });
  }, [value, disabled, onSend]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // IME composition check - do not send while composing
    if (e.nativeEvent.isComposing || isComposing) return;

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
    // Shift+Enter → default behavior (newline)
  };

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newValue = e.target.value;
    if (newValue.length <= MAX_CHARS) {
      setValue(newValue);
    }
    adjustHeight();
  };

  const canSend = value.trim().length > 0 && !disabled;

  return (
    <div className="border-t border-border p-4">
      <div className="relative flex items-end rounded-3xl border border-border bg-background shadow-sm focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-1">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onCompositionStart={() => setIsComposing(true)}
          onCompositionEnd={() => setIsComposing(false)}
          placeholder="메시지를 입력하세요..."
          disabled={disabled}
          rows={1}
          className="flex-1 resize-none bg-transparent px-4 py-3 text-sm outline-none placeholder:text-muted-foreground disabled:opacity-50 max-h-[144px]"
          style={{ minHeight: '44px' }}
        />
        <button
          type="button"
          onClick={handleSend}
          disabled={!canSend}
          className="flex-shrink-0 m-1.5 p-2 rounded-full bg-teal-600 text-white hover:bg-teal-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          aria-label="메시지 전송"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
      {value.length > MAX_CHARS * 0.9 && (
        <p className="text-xs text-muted-foreground text-right mt-1">
          {value.length}/{MAX_CHARS}
        </p>
      )}
    </div>
  );
}
