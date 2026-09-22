# S171 attempt-02 provenance errata

The Godot fixture reached READY, OPEN, CLOSE, and EXIT markers in raw stdout. CDB attached far enough to emit its initial break, then stalled in `.reload /f` while loading symbols before `CDB_ATTACHED` and htrace commands. The coordinator terminated only the attempt-owned runner, CDB, and Godot PIDs after the bounded timeout. Wrapper target/CDB exits are therefore UNKNOWN; this packet is diagnostic failure with AUTHORITY=0 and remains outside F13/F14/GT06 acceptance.
