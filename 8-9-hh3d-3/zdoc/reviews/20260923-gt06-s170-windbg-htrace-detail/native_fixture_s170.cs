using System;
using System.Runtime.InteropServices;

internal static class NativeFixtureS170
{
    private static readonly IntPtr InvalidHandleValue = new IntPtr(-1);
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern IntPtr CreateEventW(IntPtr a, bool manual, bool initial, string name);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr CreateIoCompletionPort(IntPtr file, IntPtr existing, UIntPtr key, uint threads);
    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)] private static extern bool CloseHandle(IntPtr handle);
    [DllImport("kernel32.dll")] private static extern uint GetCurrentProcessId();
    [DllImport("kernel32.dll")] private static extern void DebugBreak();
    private static string Hex(IntPtr x) { return "0x" + x.ToInt64().ToString("X"); }
    private static void Emit(string kind, string body) { Console.WriteLine("{\"kind\":\"" + kind + "\"," + body + "}"); Console.Out.Flush(); }
    private static IntPtr Event() { IntPtr h = CreateEventW(IntPtr.Zero, true, false, null); Emit(h == IntPtr.Zero ? "error" : "open", h == IntPtr.Zero ? "\"operation\":\"CreateEventW\",\"win32_error\":" + Marshal.GetLastWin32Error() : "\"type\":\"Event\",\"handle\":\"" + Hex(h) + "\""); return h; }
    private static IntPtr Completion() { IntPtr h = CreateIoCompletionPort(InvalidHandleValue, IntPtr.Zero, UIntPtr.Zero, 1); Emit(h == IntPtr.Zero ? "error" : "open", h == IntPtr.Zero ? "\"operation\":\"CreateIoCompletionPort\",\"win32_error\":" + Marshal.GetLastWin32Error() : "\"type\":\"IoCompletion\",\"handle\":\"" + Hex(h) + "\""); return h; }
    private static bool CloseOne(string type, ref IntPtr h) { if (h == IntPtr.Zero) return true; IntPtr old = h; bool ok = CloseHandle(h); h = IntPtr.Zero; Emit("close", "\"type\":\"" + type + "\",\"handle\":\"" + Hex(old) + "\",\"ok\":" + (ok ? "true" : "false") + ",\"win32_error\":" + (ok ? 0 : Marshal.GetLastWin32Error())); return ok; }
    public static int Main() {
        Emit("start", "\"pid\":" + GetCurrentProcessId() + ",\"fixture\":\"s170-htrace-detail\"");
        Emit("ready", "\"pid\":" + GetCurrentProcessId() + ",\"break_before_open\":true");
        if (!String.Equals((Console.ReadLine() ?? "").Trim(), "break_ready", StringComparison.OrdinalIgnoreCase)) return 2;
        DebugBreak();
        if (!String.Equals((Console.ReadLine() ?? "").Trim(), "open", StringComparison.OrdinalIgnoreCase)) return 3;
        IntPtr ev = Event(); IntPtr io = Completion(); bool clean = ev != IntPtr.Zero && io != IntPtr.Zero; int closed = 0;
        for (int i = 0; i < 16; i++) { IntPtr h = Event(); if (h != IntPtr.Zero && CloseHandle(h)) closed++; else clean = false; }
        Emit("open_result", "\"event_open\":" + (ev != IntPtr.Zero ? "true" : "false") + ",\"iocp_open\":" + (io != IntPtr.Zero ? "true" : "false") + ",\"churn_closed\":" + closed); DebugBreak();
        clean = CloseOne("Event", ref ev) && CloseOne("IoCompletion", ref io) && clean; Emit("close_result", "\"clean\":" + (clean ? "true" : "false")); DebugBreak(); Emit("exit", "\"ok\":" + (clean ? "true" : "false") + ",\"reason\":\"cdb_htrace_detail\""); return clean ? 0 : 1;
    }
}
