type BoatPromptProps = {
  visible: boolean;
  boarded: boolean;
};

export function BoatPrompt({ visible, boarded }: BoatPromptProps) {
  if (!visible) {
    return null;
  }

  return (
    <p className="boat-prompt" role="status">
      {boarded ? "E — xuống thuyền" : "E — lên thuyền"}
    </p>
  );
}
