# S210 packet correction

This Authority=0 correction packet preserves the sealed S208 terminal packet and adds role-specific receipt copies that were flattened under two names in the historical summary packet. The raw campaign directory and sealed archive are unchanged.

The selected files are byte-checked against the sealed raw manifest. `receipts/stderr.txt` remains authoritative in the raw archive because the historical Git blob had newline normalization (2,419 bytes) while the raw member is 2,448 bytes. `.gitattributes` prevents new text normalization in this correction packet.

This is metadata/evidence packaging only. It does not alter runtime source, the S209 campaign, the GT06 gate, thresholds, timeout, profile, counter, RSS policy, or acceptance status.