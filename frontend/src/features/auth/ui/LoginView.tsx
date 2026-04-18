import { Eye, EyeOff, LockKeyhole, UserRound } from "lucide-react";
import { FormEvent, useState } from "react";

import { AppLogo } from "../../../shared/ui/AppLogo";
import type { LoginErrorState } from "../model/useAuthSession";

interface LoginViewProps {
  error: LoginErrorState;
  isSubmitting: boolean;
  onClearError: () => void;
  onSubmit: (username: string, password: string) => void | Promise<void>;
}

export function LoginView({ error, isSubmitting, onClearError, onSubmit }: LoginViewProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [passwordVisible, setPasswordVisible] = useState(false);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void onSubmit(username.trim(), password);
  }

  return (
    <section className="relative flex min-h-[100dvh] items-start justify-center overflow-hidden bg-app-bg px-4 pb-10 pt-[12vh] text-app-text md:pt-[16vh]">
      <div className="relative z-10 flex w-full max-w-[408px] flex-col items-center gap-5">
        <div className="flex flex-col items-center gap-4 text-center">
          <AppLogo className="h-10 w-10 text-[#13227a]" />
          <div className="flex flex-col items-center gap-3">
            <h1 className="text-center text-[28px] font-semibold leading-none tracking-[-0.04em] md:text-[40px]">
              欢迎使用 Chatchat
            </h1>
          </div>
        </div>

        <form
          className="w-full rounded-[8px] border border-app-border bg-app-panel px-8 py-9"
          onSubmit={handleSubmit}
        >
          <div className="flex flex-col gap-6">
            <label className="flex flex-col gap-2.5">
              <span className="text-[14px] font-medium text-app-text">账号</span>
              <span className="flex items-center gap-3 rounded-[8px] border border-app-border bg-app-panel-strong px-4 py-4 text-app-muted transition focus-within:border-app-border-strong">
                <UserRound className="size-4 shrink-0 text-app-muted" />
                <input
                  autoComplete="username"
                  className="w-full bg-transparent text-[15px] text-app-text placeholder:text-app-muted"
                  onChange={(event) => {
                    if (error.username || error.password || error.form) {
                      onClearError();
                    }
                    setUsername(event.target.value);
                  }}
                  placeholder="输入账号"
                  value={username}
                />
              </span>
              {error.username ? (
                <div aria-live="polite" className="text-[13px] leading-5 text-app-danger">
                  {error.username}
                </div>
              ) : null}
            </label>

            <label className="flex flex-col gap-2.5">
              <span className="text-[14px] font-medium text-app-text">密码</span>
              <span className="flex items-center gap-3 rounded-[8px] border border-app-border bg-app-panel-strong px-4 py-4 text-app-muted transition focus-within:border-app-border-strong">
                <LockKeyhole className="size-4 shrink-0 text-app-muted" />
                <input
                  autoComplete="current-password"
                  className="w-full bg-transparent text-[15px] text-app-text placeholder:text-app-muted"
                  onChange={(event) => {
                    if (error.username || error.password || error.form) {
                      onClearError();
                    }
                    setPassword(event.target.value);
                  }}
                  placeholder="输入密码"
                  type={passwordVisible ? "text" : "password"}
                  value={password}
                />
                <button
                  aria-label={passwordVisible ? "隐藏密码" : "显示密码"}
                  className="shrink-0 text-app-muted transition hover:text-app-text"
                  onClick={() => setPasswordVisible((value) => !value)}
                  type="button"
                >
                  {passwordVisible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </span>
              {error.password ? (
                <div aria-live="polite" className="text-[13px] leading-5 text-app-danger">
                  {error.password}
                </div>
              ) : null}
            </label>

            <button
              className="rounded-[8px] bg-app-accent-strong px-4 py-4 text-[15px] font-medium text-white transition hover:opacity-92 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isSubmitting || !username.trim() || !password}
              type="submit"
            >
              {isSubmitting ? "登录中..." : "登录"}
            </button>

            {error.form ? (
              <div aria-live="polite" className="text-[13px] leading-5 text-app-danger">
                {error.form}
              </div>
            ) : null}
          </div>
        </form>

        <div className="text-center text-[13px] leading-6 text-app-muted">
          继续即表示您同意使用条款和隐私政策
        </div>
      </div>
    </section>
  );
}
