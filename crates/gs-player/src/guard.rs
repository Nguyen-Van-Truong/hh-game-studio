//! Watchdog and memory-guard helpers (MASTER 6.5).

/// Single simulate frame slower than this → exit 13 `SCRIPT_HANG`.
pub const WATCHDOG_FRAME_MS: u64 = 2000;
/// Process RAM above this → warning log (MASTER 6.5).
pub const RAM_WARN_BYTES: u64 = 1024 * 1024 * 1024;
/// Process RAM (or injected counter) above this → exit 14 `OOM_GUARD`.
pub const OOM_GUARD_BYTES: u64 = 2 * 1024 * 1024 * 1024;
pub const EXIT_SCRIPT_HANG: i32 = 13;
pub const EXIT_OOM_GUARD: i32 = 14;

/// True when a single `step()` / simulate frame exceeded the 2000ms watchdog.
pub fn watchdog_trip(elapsed_ms: u64) -> bool {
    elapsed_ms > WATCHDOG_FRAME_MS
}

/// True when observed bytes (RSS or an injected counter) exceed the limit.
pub fn memory_guard_trip(used_bytes: u64, limit_bytes: u64) -> bool {
    used_bytes > limit_bytes
}

/// `GS_TEST_HANG_MS` — test-only fake elapsed for the next simulate frame.
pub fn test_hang_ms_from_env() -> Option<u64> {
    let raw = std::env::var("GS_TEST_HANG_MS").ok()?;
    raw.parse::<u64>().ok().filter(|ms| *ms > 0)
}

/// Best-effort working-set / RSS. `None` if the OS query fails.
///
/// Windows uses `WorkingSetSize` (can include shared pages). Tests should
/// inject a counter rather than allocating 2GB.
pub fn process_rss_bytes() -> Option<u64> {
    #[cfg(windows)]
    {
        windows_working_set_bytes()
    }
    #[cfg(not(windows))]
    {
        proc_vm_rss_bytes()
    }
}

#[cfg(windows)]
fn windows_working_set_bytes() -> Option<u64> {
    #[repr(C)]
    struct ProcessMemoryCounters {
        cb: u32,
        page_fault_count: u32,
        peak_working_set_size: usize,
        working_set_size: usize,
        quota_peak_paged_pool_usage: usize,
        quota_paged_pool_usage: usize,
        quota_peak_non_paged_pool_usage: usize,
        quota_non_paged_pool_usage: usize,
        pagefile_usage: usize,
        peak_pagefile_usage: usize,
    }

    extern "system" {
        fn GetCurrentProcess() -> *mut core::ffi::c_void;
        fn K32GetProcessMemoryInfo(
            process: *mut core::ffi::c_void,
            ppsmem_counters: *mut ProcessMemoryCounters,
            cb: u32,
        ) -> i32;
    }

    let mut counters = ProcessMemoryCounters {
        cb: u32::try_from(std::mem::size_of::<ProcessMemoryCounters>()).unwrap_or(0),
        page_fault_count: 0,
        peak_working_set_size: 0,
        working_set_size: 0,
        quota_peak_paged_pool_usage: 0,
        quota_paged_pool_usage: 0,
        quota_peak_non_paged_pool_usage: 0,
        quota_non_paged_pool_usage: 0,
        pagefile_usage: 0,
        peak_pagefile_usage: 0,
    };
    // SAFETY: `GetCurrentProcess` is a pseudo-handle; `cb` is this struct's size.
    let ok = unsafe { K32GetProcessMemoryInfo(GetCurrentProcess(), &mut counters, counters.cb) };
    if ok == 0 {
        None
    } else {
        Some(counters.working_set_size as u64)
    }
}

#[cfg(not(windows))]
fn proc_vm_rss_bytes() -> Option<u64> {
    let text = std::fs::read_to_string("/proc/self/status").ok()?;
    for line in text.lines() {
        let Some(rest) = line.strip_prefix("VmRSS:") else {
            continue;
        };
        let kb: u64 = rest.split_whitespace().next()?.parse().ok()?;
        return Some(kb.saturating_mul(1024));
    }
    None
}

#[cfg(test)]
mod tests {
    use super::{memory_guard_trip, watchdog_trip, OOM_GUARD_BYTES, WATCHDOG_FRAME_MS};

    #[test]
    fn watchdog_trips_only_over_2000ms() {
        assert!(!watchdog_trip(WATCHDOG_FRAME_MS));
        assert!(!watchdog_trip(0));
        assert!(watchdog_trip(WATCHDOG_FRAME_MS + 1));
    }

    #[test]
    fn memory_guard_trips_over_two_gigabytes() {
        assert!(!memory_guard_trip(OOM_GUARD_BYTES, OOM_GUARD_BYTES));
        assert!(memory_guard_trip(OOM_GUARD_BYTES + 1, OOM_GUARD_BYTES));
        assert!(!memory_guard_trip(0, OOM_GUARD_BYTES));
    }
}
