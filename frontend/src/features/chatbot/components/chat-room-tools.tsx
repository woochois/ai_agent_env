interface ChatRoomToolsProps {
  toolCalls: ReadonlyArray<string | null | undefined> | null | undefined;
  sources: ReadonlyArray<string | null | undefined> | null | undefined;
}

export function ChatRoomTools({ toolCalls, sources }: ChatRoomToolsProps) {
  const validTools = toolCalls?.filter((t): t is string => !!t) ?? [];
  const validSources = sources?.filter((s): s is string => !!s) ?? [];

  if (validTools.length === 0 && validSources.length === 0) return null;

  return (
    <div className="space-y-2 pl-10 pb-2">
      {validTools.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs font-medium text-muted-foreground">사용된 도구</p>
          <div className="flex flex-wrap gap-1.5">
            {validTools.map((tool, idx) => (
              <span
                key={idx}
                className="inline-flex items-center gap-1 rounded-full bg-blue-100 dark:bg-blue-900/30 px-3 py-1 text-xs font-medium text-blue-700 dark:text-blue-300"
              >
                🔧 {tool}
              </span>
            ))}
          </div>
        </div>
      )}

      {validSources.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs font-medium text-muted-foreground">참고 소스</p>
          <div className="flex flex-wrap gap-1.5">
            {validSources.map((source, idx) => (
              <div
                key={idx}
                className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 text-xs shadow-sm"
              >
                <span className="text-muted-foreground">📄</span>
                <span className="text-foreground">{source}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
