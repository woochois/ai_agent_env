import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Users,
  MessageSquare,
  FileText,
  Moon,
  Sun,
  LogOut,
  CircleDot,
} from 'lucide-react';
import { useTheme } from './theme-provider';
import { useAuth } from './auth-provider';
import { useHealth } from '@/hooks/use-health';
import { cn } from '@/lib/utils';

type HealthStatus = 'healthy' | 'degraded' | 'unhealthy';

interface NavItem {
  label: string;
  icon: React.ReactNode;
  path: string;
  external?: boolean;
}

const navItems: NavItem[] = [
  { label: '대시보드', icon: <LayoutDashboard className="h-5 w-5" />, path: '/' },
  { label: '에이전트', icon: <Users className="h-5 w-5" />, path: '/agents' },
  { label: '플레이그라운드', icon: <MessageSquare className="h-5 w-5" />, path: '/playground' },
  { label: 'API 문서', icon: <FileText className="h-5 w-5" />, path: '/docs', external: true },
];

const healthConfig: Record<HealthStatus, { label: string; colorClass: string }> = {
  healthy: { label: '정상', colorClass: 'text-green-500' },
  degraded: { label: '부분 장애', colorClass: 'text-yellow-500' },
  unhealthy: { label: '연결 실패', colorClass: 'text-red-500' },
};

export function ModernNav() {
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();
  const { logout } = useAuth();

  const healthStatus = useHealth();

  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  };

  const { label: healthLabel, colorClass: healthColorClass } = healthConfig[healthStatus];

  return (
    <nav className="flex h-screen w-64 flex-col border-r border-border bg-sidebar-background text-sidebar-foreground">
      {/* Top: Logo area */}
      <div className="flex h-16 items-center gap-2 border-b border-border px-6">
        <MessageSquare className="h-6 w-6 text-primary" />
        <span className="text-lg font-semibold">Playground</span>
      </div>

      {/* Middle: Menu items */}
      <div className="flex-1 space-y-1 px-3 py-4">
        {navItems.map((item) =>
          item.external ? (
            <a
              key={item.path}
              href={item.path}
              target="_blank"
              rel="noopener noreferrer"
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                'text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground'
              )}
            >
              {item.icon}
              {item.label}
            </a>
          ) : (
            <Link
              key={item.path}
              to={item.path}
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                isActive(item.path)
                  ? 'bg-sidebar-primary text-sidebar-primary-foreground'
                  : 'text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground'
              )}
            >
              {item.icon}
              {item.label}
            </Link>
          )
        )}
      </div>

      {/* Bottom: Health badge, theme toggle, user info + logout */}
      <div className="border-t border-border px-3 py-4 space-y-3">
        {/* Health badge */}
        <div className="flex items-center gap-2 px-3 py-1.5">
          <CircleDot className={cn('h-4 w-4', healthColorClass)} />
          <span className={cn('text-xs font-medium', healthColorClass)}>
            {healthLabel}
          </span>
        </div>

        {/* Theme toggle */}
        <button
          onClick={toggleTheme}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-sidebar-foreground/70 transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
        >
          {theme === 'dark' ? (
            <Sun className="h-5 w-5" />
          ) : (
            <Moon className="h-5 w-5" />
          )}
          {theme === 'dark' ? '라이트 모드' : '다크 모드'}
        </button>

        {/* User info + logout */}
        <div className="flex items-center gap-3 rounded-lg px-3 py-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-semibold">
            A
          </div>
          <div className="flex-1 min-w-0">
            <p className="truncate text-sm font-medium text-sidebar-foreground">Admin</p>
          </div>
          <button
            onClick={logout}
            className="rounded-md p-1.5 text-sidebar-foreground/50 transition-colors hover:bg-destructive/10 hover:text-destructive"
            title="로그아웃"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </nav>
  );
}
