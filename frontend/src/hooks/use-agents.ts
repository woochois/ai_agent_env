import { useState, useEffect } from 'react';

interface AgentInfo {
  type: string;
  displayName: string;
}

export function useAgents() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchAgents = async () => {
      try {
        const response = await fetch('/agent/supervisor/agents');
        if (!response.ok) throw new Error('Failed to fetch agents');
        const data = await response.json();
        // Transform: remove _agent suffix, replace _ with space
        const agentList = Object.keys(data.agents || data).map(key => ({
          type: key,
          displayName: key.replace(/_agent$/, '').replace(/_/g, ' '),
        }));
        setAgents(agentList);
      } catch (err: any) {
        setError(err.message || '에이전트 로드 실패');
      } finally {
        setIsLoading(false);
      }
    };
    fetchAgents();
  }, []);

  return { agents, error, isLoading };
}
