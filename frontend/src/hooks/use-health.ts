import { useState, useEffect } from 'react';

type HealthStatus = 'healthy' | 'degraded' | 'unhealthy';

export function useHealth() {
  const [status, setStatus] = useState<HealthStatus>('healthy');

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await fetch('/health');
        if (!response.ok) {
          setStatus('unhealthy');
          return;
        }
        const data = await response.json();
        setStatus(data.status || 'healthy');
      } catch {
        setStatus('unhealthy');
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, 30000); // 30 second polling
    return () => clearInterval(interval);
  }, []);

  return status;
}
