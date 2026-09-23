# S194 external sampler diagnostic

S194 is a bounded, diagnostic-only idle-editor run. A separate Python observer process opened the Godot target using PID, process-start time, and executable-image identity, then sampled `GetProcessHandleCount` every 250 ms. This is distinct from S188, whose retained `ProcessProbe` in the driver performed the sampling.

The pinned Godot 4.7.2 editor completed the 90-second idle plugin naturally (actual target exit 0); the external sampler exited 0 after 387 samples, and the owned Job was zero/closed with no cleanup error. Raw evidence is retained under the ignored `.local` review path and archived with a manifest.

The external route still showed non-monotonic counter variation after startup. This separates sampler-process ownership from the observed target counter but does not identify a kernel handle owner, prove a leak or root cause, or satisfy GT06. GT06 remains the frozen 10 fresh pairs × 35 batches gate.
