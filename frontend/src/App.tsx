import { Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@/components/theme-provider';
import { AuthProvider } from '@/components/auth-provider';
import { ProtectedRoute } from '@/components/protected-route';
import { ModernNav } from '@/components/modern-nav';
import { LoginPage } from '@/features/auth/pages/login-page';
import { ChatbotListPage } from '@/features/chatbot/pages/chatbot-list-page';
import { ChatbotDetailPage } from '@/features/chatbot/pages/chatbot-detail-page';
import { Toaster } from 'sonner';

function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <ModernNav />
      <main className="flex-1 overflow-hidden">{children}</main>
    </div>
  );
}

export function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <Toaster position="top-right" richColors />
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <RootLayout>
                  <Routes>
                    <Route path="/" element={<ChatbotListPage />} />
                    <Route path="/chatbot/:id" element={<ChatbotDetailPage />} />
                  </Routes>
                </RootLayout>
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </ThemeProvider>
  );
}
