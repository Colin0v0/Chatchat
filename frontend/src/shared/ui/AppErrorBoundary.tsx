import { Component, type ErrorInfo, type ReactNode } from "react";

type AppErrorBoundaryProps = {
  children: ReactNode;
};

type AppErrorBoundaryState = {
  error: Error | null;
};

export class AppErrorBoundary extends Component<AppErrorBoundaryProps, AppErrorBoundaryState> {
  state: AppErrorBoundaryState = {
    error: null,
  };

  static getDerivedStateFromError(error: Error): AppErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("React render failed", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <section className="flex min-h-[100dvh] items-center justify-center bg-app-bg px-6 text-app-text">
          <div className="w-full max-w-[420px] rounded-lg border border-black/10 bg-app-panel p-5 shadow-sm">
            <h1 className="text-[18px] font-semibold">页面渲染出错</h1>
            <p className="mt-2 text-[14px] leading-6 text-app-muted">
              当前视图遇到异常，请刷新页面后继续。
            </p>
            <button
              className="mt-4 rounded-md bg-app-text px-4 py-2 text-[14px] font-medium text-white"
              onClick={() => window.location.reload()}
              type="button"
            >
              刷新页面
            </button>
          </div>
        </section>
      );
    }

    return this.props.children;
  }
}
