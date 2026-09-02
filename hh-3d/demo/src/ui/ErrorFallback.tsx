import { Component, type ErrorInfo, type ReactNode } from "react";
import { landmarks } from "../scene/sceneConfig";

export type FallbackReason = "webgl" | "runtime" | "forced";

type ErrorFallbackProps = {
  reason: FallbackReason;
  message?: string;
  onRetry3d?: () => void;
};

export function ErrorFallback({
  reason,
  message,
  onRetry3d,
}: ErrorFallbackProps) {
  const heading =
    reason === "runtime"
      ? "Hòn Gió không thể mở chế độ 3D"
      : "Hòn Gió — bản tĩnh";

  const howToContinue =
    reason === "runtime"
      ? "Canvas 3D gặp lỗi lúc chạy. Bạn vẫn có thể xem danh sách địa danh bên dưới hoặc thử mở lại 3D."
      : "WebGL không khả dụng hoặc bạn đang xem bản tĩnh. Bạn vẫn có thể đọc mọi địa danh và thử lại 3D khi trình duyệt cho phép.";

  return (
    <section className="fallback-panel" aria-labelledby="fallback-heading">
      <h1 id="fallback-heading">{heading}</h1>
      <p className="fallback-status">Demo tương tác · chế độ dự phòng</p>
      <p>{howToContinue}</p>
      {message ? <p className="fallback-message">{message}</p> : null}
      <img
        className="fallback-image"
        src="/fallback-hon-gio.svg"
        alt="Sơ đồ tĩnh Hòn Gió có hải đăng, bến gỗ, thuyền nhỏ và nhà mái ngói."
      />
      <h2>Địa danh</h2>
      <ul className="fallback-landmarks">
        {landmarks.map((landmark) => (
          <li key={landmark.id}>
            <strong>{landmark.title}</strong>
            <span> — {landmark.description}</span>
          </li>
        ))}
      </ul>
      <p>
        Cách tiếp tục trong 3D: WASD để đi bộ, E để lên thúng, kéo chuột để
        xoay, rồi chọn Chơi hoặc Toàn cảnh.
      </p>
      {onRetry3d ? (
        <button type="button" className="ui-button" onClick={onRetry3d}>
          Mở lại 3D
        </button>
      ) : null}
    </section>
  );
}

type ErrorBoundaryProps = {
  children: ReactNode;
  onError?: (error: Error) => void;
};

type ErrorBoundaryState = {
  error: Error | null;
};

export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  public state: ErrorBoundaryState = { error: null };

  public static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  public componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("Hòn Gió runtime error", error, info.componentStack);
    this.props.onError?.(error);
  }

  public override render(): ReactNode {
    if (this.state.error) {
      return null;
    }

    return this.props.children;
  }
}
