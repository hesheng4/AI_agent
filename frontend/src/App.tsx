// 根组件 — 路由配置 + React.lazy 代码分割 + ErrorBoundary
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { type ReactNode, lazy, Suspense } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './auth';
import ErrorBoundary from './components/ErrorBoundary';
import PWAInstallPrompt from './components/PWAInstallPrompt';

// TanStack Query 客户端 — 全局缓存 + 请求去重 + 自动后台刷新
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5_000,     // 5s 内复用缓存，不重新请求
      gcTime: 5 * 60_000,   // 5min 后垃圾回收
      retry: 2,             // 失败重试 2 次
      refetchOnWindowFocus: false,  // 切回窗口不自动刷新（避免干扰）
    },
  },
});

// 首屏关键页面 — 直接导入
import Hero from './sections/Hero';
import Login from './pages/Login';
import Layout from './components/Layout';

// 懒加载 — 按路由分割
const Literature = lazy(() => import('./pages/Literature'));
const Library = lazy(() => import('./pages/Library'));
const Network = lazy(() => import('./pages/Network'));
const DataAnalysis = lazy(() => import('./pages/DataAnalysis'));
const Writing = lazy(() => import('./pages/Writing'));
const Experiment = lazy(() => import('./pages/Experiment'));
const Profile = lazy(() => import('./pages/Profile'));
// Batch 1
const Coordinator = lazy(() => import('./pages/Coordinator'));
const CoordinatorAudit = lazy(() => import('./pages/CoordinatorAudit'));
const Reader = lazy(() => import('./pages/Reader'));
const Reviewer = lazy(() => import('./pages/Reviewer'));
const ResponsePage = lazy(() => import('./pages/Response'));
const ReviewLoopPage = lazy(() => import('./pages/ReviewLoop'));
const CitationPage = lazy(() => import('./pages/Citation'));
const ExportPage = lazy(() => import('./pages/Export'));
// Batch 3
const FigurePage = lazy(() => import('./pages/Figure'));
const Paper2PPT = lazy(() => import('./pages/Paper2PPT'));
const PaperToPatent = lazy(() => import('./pages/PaperToPatent'));
const CoverLetter = lazy(() => import('./pages/CoverLetter'));
const MethodsPage = lazy(() => import('./pages/MethodsPage'));
const SubmissionPackagePage = lazy(() => import('./pages/SubmissionPackage'));
const PolishingPage = lazy(() => import('./pages/PolishingPage'));
const StatsPage = lazy(() => import('./pages/StatsPage'));
const DataAvailability = lazy(() => import('./pages/DataAvailability'));
// 昇腾
const AscendOverview = lazy(() => import('./pages/ascend/AscendOverview'));
const Alignment = lazy(() => import('./pages/ascend/Alignment'));
const Profiling = lazy(() => import('./pages/ascend/Profiling'));
const PerfTuning = lazy(() => import('./pages/ascend/PerfTuning'));
const Toolchain = lazy(() => import('./pages/ascend/Toolchain'));
const Validator = lazy(() => import('./pages/ascend/Validator'));
const Debugging = lazy(() => import('./pages/ascend/Debugging'));
const HistoryToSkill = lazy(() => import('./pages/ascend/HistoryToSkill'));
const Adaptation = lazy(() => import('./pages/ascend/Adaptation'));
const AgentGenerator = lazy(() => import('./pages/AgentGenerator'));
const WorkflowEditor = lazy(() => import('./pages/WorkflowEditor'));

// 加载占位
function PageLoader() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <i className="fas fa-circle-notch animate-spin text-2xl text-copper" />
    </div>
  );
}

// 路由守卫
function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-ink-dark">
        <i className="fas fa-circle-notch animate-spin text-2xl text-copper" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  return <>{children}</>;
}

function RedirectIfAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) return <Navigate to="/app" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
      <AuthProvider>
      <PWAInstallPrompt />
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Hero />} />
            <Route path="/login" element={<RedirectIfAuth><Login /></RedirectIfAuth>} />

            <Route path="/app" element={<RequireAuth><Layout /></RequireAuth>}>
              <Route index element={<Navigate to="/app/literature" replace />} />
              {/* 科研工作台 */}
              <Route path="coordinator" element={<Suspense fallback={<PageLoader />}><Coordinator /></Suspense>} />
              <Route path="audit" element={<Suspense fallback={<PageLoader />}><CoordinatorAudit /></Suspense>} />
              <Route path="literature" element={<Suspense fallback={<PageLoader />}><Literature /></Suspense>} />
              <Route path="reader" element={<Suspense fallback={<PageLoader />}><Reader /></Suspense>} />
              <Route path="library" element={<Suspense fallback={<PageLoader />}><Library /></Suspense>} />
              <Route path="network" element={<Suspense fallback={<PageLoader />}><Network /></Suspense>} />
              <Route path="citation" element={<Suspense fallback={<PageLoader />}><CitationPage /></Suspense>} />
              <Route path="data" element={<Suspense fallback={<PageLoader />}><DataAnalysis /></Suspense>} />
              <Route path="writing" element={<Suspense fallback={<PageLoader />}><Writing /></Suspense>} />
              <Route path="reviewer" element={<Suspense fallback={<PageLoader />}><Reviewer /></Suspense>} />
              <Route path="response" element={<Suspense fallback={<PageLoader />}><ResponsePage /></Suspense>} />
              <Route path="review-loop" element={<Suspense fallback={<PageLoader />}><ReviewLoopPage /></Suspense>} />
              <Route path="experiment" element={<Suspense fallback={<PageLoader />}><Experiment /></Suspense>} />
              <Route path="export" element={<Suspense fallback={<PageLoader />}><ExportPage /></Suspense>} />
              <Route path="figure" element={<Suspense fallback={<PageLoader />}><FigurePage /></Suspense>} />
              <Route path="paper2ppt" element={<Suspense fallback={<PageLoader />}><Paper2PPT /></Suspense>} />
              <Route path="paper-to-patent" element={<Suspense fallback={<PageLoader />}><PaperToPatent /></Suspense>} />
              <Route path="cover" element={<Suspense fallback={<PageLoader />}><CoverLetter /></Suspense>} />
              <Route path="methods" element={<Suspense fallback={<PageLoader />}><MethodsPage /></Suspense>} />
              <Route path="submission-package" element={<Suspense fallback={<PageLoader />}><SubmissionPackagePage /></Suspense>} />
              <Route path="polishing" element={<Suspense fallback={<PageLoader />}><PolishingPage /></Suspense>} />
              <Route path="stats" element={<Suspense fallback={<PageLoader />}><StatsPage /></Suspense>} />
              <Route path="data-availability" element={<Suspense fallback={<PageLoader />}><DataAvailability /></Suspense>} />
              {/* 个人中心 */}
              <Route path="profile" element={<Suspense fallback={<PageLoader />}><Profile /></Suspense>} />
              {/* 昇腾工作台 */}
              <Route path="ascend" element={<Suspense fallback={<PageLoader />}><AscendOverview /></Suspense>} />
              <Route path="alignment" element={<Suspense fallback={<PageLoader />}><Alignment /></Suspense>} />
              <Route path="profiling" element={<Suspense fallback={<PageLoader />}><Profiling /></Suspense>} />
              <Route path="perf-tuning" element={<Suspense fallback={<PageLoader />}><PerfTuning /></Suspense>} />
              <Route path="toolchain" element={<Suspense fallback={<PageLoader />}><Toolchain /></Suspense>} />
              <Route path="validator" element={<Suspense fallback={<PageLoader />}><Validator /></Suspense>} />
              <Route path="debugging" element={<Suspense fallback={<PageLoader />}><Debugging /></Suspense>} />
              <Route path="history-to-skill" element={<Suspense fallback={<PageLoader />}><HistoryToSkill /></Suspense>} />
              <Route path="adaptation" element={<Suspense fallback={<PageLoader />}><Adaptation /></Suspense>} />
              <Route path="agent-generator" element={<Suspense fallback={<PageLoader />}><AgentGenerator /></Suspense>} />
              <Route path="workflow-editor" element={<Suspense fallback={<PageLoader />}><WorkflowEditor /></Suspense>} />
            </Route>

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
