# S145 coupled 64KiB candidate (diagnostic only)

S144 stock control held host handles constant while S143 candidate had one +1
transient growth. S145 keeps the proven <=2047B hash updates but reduces the
disk-read chunk from 1MiB to 64KiB to reduce transient pressure. Original native,
profile, workload and gates are unchanged. Seven coupled batches only; no F13/F14,
no formal PASS, no leak/root-cause claim.
