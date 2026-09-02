import { sceneConfig } from "../scene/sceneConfig";
import { VIEW_MODE_IDS, type ViewMode } from "../scene/viewMode";

type CameraNavProps = {
  viewMode: ViewMode;
  onChange: (id: ViewMode) => void;
};

const LABELS: Record<ViewMode, string> = {
  play: "Chơi",
  overview: "Toàn cảnh",
  harbor: "Bến",
  lighthouse: "Hải đăng",
  island: "Đảo",
};

export function CameraNav({ viewMode, onChange }: CameraNavProps) {
  return (
    <nav className="camera-nav" aria-label="Máy quay">
      <span className="dock-title">Góc nhìn</span>
      <div className="dock-actions">
        {VIEW_MODE_IDS.map((id) => {
          const title =
            id === "play" ? "Theo nhân vật" : sceneConfig.presets[id].label;
          return (
            <button
              key={id}
              type="button"
              className="ui-button"
              title={title}
              aria-pressed={viewMode === id}
              onClick={() => {
                onChange(id);
              }}
            >
              {LABELS[id]}
            </button>
          );
        })}
      </div>
    </nav>
  );
}
