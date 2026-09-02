export const LANDMARK_IDS = [
  "lighthouse",
  "harbor",
  "boat",
  "houses",
] as const;

export type LandmarkId = (typeof LANDMARK_IDS)[number];

export type SelectedObject = {
  id: LandmarkId;
  title: string;
  description: string;
};

export type SelectHandler = (object: SelectedObject | null) => void;
