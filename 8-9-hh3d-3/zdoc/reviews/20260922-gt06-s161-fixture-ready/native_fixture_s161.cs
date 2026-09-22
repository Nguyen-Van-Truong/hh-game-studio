using System;
using System.Runtime.InteropServices;

internal static class NativeFixtureS161
{
    private static readonly IntPtr InvalidHandleValue = new IntPtr(-1);
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern IntPtr CreateEventW(IntPtr attributes, bool manualReset, bool initialState, string name);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr CreateIoCompletionPort(IntPtr fileHandle, IntPtr existingPort, UIntPtr completionKey, uint threads);
    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CloseHandle(IntPtr handle);
    [DllImport("kernel32.dll")]
    private static extern uint GetCurrentProcessId();

    private static string Hex(IntPtr value) { return "0x" + value.ToInt64().ToString("X"); }
    private static void Emit(string kind, string body) {
        Console.WriteLine("{\"kind\":\"" + kind + "\"," + body + "}");
        Console.Out.Flush();
    }
    private static IntPtr OpenEvent() {
        IntPtr h = CreateEventW(IntPtr.Zero, true, false, null);
        if (h == IntPtr.Zero) Emit("error", "\"operation\":\"CreateEventW\",\"win32_error\":" + Marshal.GetLastWin32Error());
        else Emit("open", "\"type\":\"Event\",\"handle\":\"" + Hex(h) + "\"");
        return h;
    }
    private static IntPtr OpenCompletion() {
        IntPtr h = CreateIoCompletionPort(InvalidHandleValue, IntPtr.Zero, UIntPtr.Zero, 1);
        if (h == IntPtr.Zero) Emit("error", "\"operation\":\"CreateIoCompletionPort\",\"win32_error\":" + Marshal.GetLastWin32Error());
        else Emit("open", "\"type\":\"IoCompletion\",\"handle\":\"" + Hex(h) + "\"");
        return h;
    }
    private static bool CloseOne(string type, ref IntPtr handle) {
        if (handle == IntPtr.Zero) { Emit("close", "\"type\":\"" + type + "\",\"state\":\"already_closed\""); return true; }
        IntPtr old = handle;
        bool ok = CloseHandle(handle);
        int error = ok ? 0 : Marshal.GetLastWin32Error();
        handle = IntPtr.Zero;
        Emit("close", "\"type\":\"" + type + "\",\"handle\":\"" + Hex(old) + "\",\"ok\":" + (ok ? "true" : "false") + ",\"win32_error\":" + error);
        return ok;
    }
    private static bool CloseAll(ref IntPtr ev, ref IntPtr iocp) {
        return CloseOne("Event", ref ev) & CloseOne("IoCompletion", ref iocp);
    }

    public static int Main() {
        IntPtr ev = IntPtr.Zero;
        IntPtr iocp = IntPtr.Zero;
        bool opened = false;
        bool clean = true;
        Emit("start", "\"pid\":" + GetCurrentProcessId() + ",\"fixture\":\"s161-native-handle-ready\",\"handles_opened\":false");
        Emit("ready", "\"pid\":" + GetCurrentProcessId() + ",\"observer_attach_before_open\":true");
        string command;
        while ((command = Console.ReadLine()) != null) {
            command = command.Trim();
            if (command.Equals("open", StringComparison.OrdinalIgnoreCase)) {
                if (opened) { Emit("error", "\"operation\":\"open\",\"message\":\"already_open\""); continue; }
                ev = OpenEvent();
                iocp = OpenCompletion();
                opened = ev != IntPtr.Zero && iocp != IntPtr.Zero;
                if (!opened) { clean = false; CloseAll(ref ev, ref iocp); }
                Emit("open_result", "\"opened\":" + (opened ? "true" : "false"));
            } else if (command.Equals("snapshot", StringComparison.OrdinalIgnoreCase)) {
                Emit("snapshot", "\"event_open\":" + (ev != IntPtr.Zero ? "true" : "false") + ",\"iocp_open\":" + (iocp != IntPtr.Zero ? "true" : "false") + ",\"opened\":" + (opened ? "true" : "false"));
            } else if (command.StartsWith("churn ", StringComparison.OrdinalIgnoreCase)) {
                int count;
                if (!int.TryParse(command.Substring(6), out count) || count < 0 || count > 8192) { Emit("error", "\"operation\":\"churn\",\"message\":\"invalid_count\""); clean = false; continue; }
                int closed = 0;
                for (int i = 0; i < count; i++) {
                    IntPtr h = CreateEventW(IntPtr.Zero, true, false, null);
                    if (h != IntPtr.Zero && CloseHandle(h)) closed++;
                }
                Emit("churn", "\"requested\":" + count + ",\"closed\":" + closed);
                if (closed != count) clean = false;
            } else if (command.Equals("close_event", StringComparison.OrdinalIgnoreCase)) {
                clean = CloseOne("Event", ref ev) && clean;
            } else if (command.Equals("close_iocp", StringComparison.OrdinalIgnoreCase)) {
                clean = CloseOne("IoCompletion", ref iocp) && clean;
            } else if (command.Equals("exit", StringComparison.OrdinalIgnoreCase)) {
                clean = CloseAll(ref ev, ref iocp) && clean;
                Emit("exit", "\"ok\":" + (clean ? "true" : "false") + ",\"reason\":\"command\"");
                return clean ? 0 : 1;
            } else {
                Emit("error", "\"operation\":\"command\",\"message\":\"unknown\"");
                clean = false;
            }
        }
        clean = CloseAll(ref ev, ref iocp) && clean;
        Emit("exit", "\"ok\":" + (clean ? "true" : "false") + ",\"reason\":\"stdin_eof\"");
        return clean ? 0 : 1;
    }
}
