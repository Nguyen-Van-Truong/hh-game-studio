# GT06 S85 failure — retained handle growth

`authority=0`; diagnostic only; not a campaign sample and not acceptance evidence.

The scheduler-owned run `gt06-s85-attribution-01` ended at batch 5 during joint observation. Baseline batch 4 had editor held handles **559**; batch 5 had **561**, so the unchanged gate `CAMPAIGN_RETAINED_COUNTER_GROWTH` correctly stopped the prefix. Editor ObjectDB stayed 71128→71128 and RSS fell 398458880→383279104 bytes, so this packet does not attribute the failure to ObjectDB or RSS.

Cleanup evidence records Job zero, closed handles and no retained owner handles. The target natural exit receipt is missing, so no exit PASS is inferred. The six partial batches are preserved only for diagnosis. Do not splice them into the official dataset or retry the same run ID.

Source closure: `e010180a1bf85b7f565e9aa39734f8551caf170a85b36c50598be556b723ce7f`; profile: `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`.
