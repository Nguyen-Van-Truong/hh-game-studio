# Keep the accepted Python/coreutils base; only relocate the pinned Godot
# binary from a Windows bind mount into the immutable Linux image layer.
FROM python@sha256:581429e3df12d76e6af4be5ab7d0e7fc2013eb57dc23d2de691411c8efdbb970
COPY --chmod=0555 Godot_v4.7.2-stable_linux.x86_64 /tool/Godot_v4.7.2-stable_linux.x86_64
