using System;
using System.Runtime.InteropServices;

internal static class NativeFixtureS169
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
    [DllImport("kernel32.dll")]
    private static extern void DebugBreak();

    private static string Hex(IntPtr value) { return "0x" + value.ToInt64().ToString("X"); }
    private static void Emit(string kind, string body)
    {
        Console.WriteLine("{\"kind\":\"" + kind + "\"," + body + "}");
        Console.Out.Flush();
    }
    private static IntPtr OpenEvent()
    {
        IntPtr handle = CreateEventW(IntPtr.Zero, true, false, null);
        if (handle == IntPtr.Zero)
            Emit("error", "\"operation\":\"CreateEventW\",\"win32_error\":" + Marshal.GetLastWin32Error());
        else
            Emit("open", "\"type\":\"Event\",\"handle\":\"" + Hex(handle) + "\"");
        return handle;
    }
    private static IntPtr OpenCompletion()
    {
        IntPtr handle = CreateIoCompletionPort(InvalidHandleValue, IntPtr.Zero, UIntPtr.Zero, 1);
        if (handle == IntPtr.Zero)
            Emit("error", "\"operation\":\"CreateIoCompletionPort\",\"win32_error\":" + Marshal.GetLastWin32Error());
        else
            Emit("open", "\"type\":\"IoCompletion\",\"handle\":\"" + Hex(handle) + "\"");
        return handle;
    }
    private static bool CloseOne(string type, ref IntPtr handle)
    {
        if (handle == IntPtr.Zero)
        {
            Emit("close", "\"type\":\"" + type + "\",\"state\":\"already_closed\"");
            return true;
        }
        IntPtr old = handle;
        bool ok = CloseHandle(handle);
        int error = ok ? 0 : Marshal.GetLastWin32Error();
        handle = IntPtr.Zero;
        Emit("close", "\"type\":\"" + type + "\",\"handle\":\"" + Hex(old) + "\",\"ok\":" + (ok ? "true" : "false") + ",\"win32_error\":" + error);
        return ok;
    }
    private static bool CloseAll(ref IntPtr ev, ref IntPtr iocp)
    {
        return CloseOne("Event", ref ev) && CloseOne("IoCompletion", ref iocp);
    }

    public static int Main()
    {
        Emit("start", "\"pid\":" + GetCurrentProcessId() + ",\"fixture\":\"s169-cdb-htrace\"");
        Emit("ready", "\"pid\":" + GetCurrentProcessId() + ",\"break_before_open\":true");
        string command = Console.ReadLine();
        if (!String.Equals(command == null ? "" : command.Trim(), "break_ready", StringComparison.OrdinalIgnoreCase))
        {
            Emit("error", "\"operation\":\"ready\",\"message\":\"missing_break_ready\"");
            return 2;
        }
        DebugBreak();
        command = Console.ReadLine();
        if (!String.Equals(command == null ? "" : command.Trim(), "open", StringComparison.OrdinalIgnoreCase))
        {
            Emit("error", "\"operation\":\"open\",\"message\":\"missing_open\"");
            return 3;
        }
        IntPtr ev = OpenEvent();
        IntPtr iocp = OpenCompletion();
        bool clean = ev != IntPtr.Zero && iocp != IntPtr.Zero;
        int closed = 0;
        for (int i = 0; i < 16; i++)
        {
            IntPtr temp = CreateEventW(IntPtr.Zero, true, false, null);
            if (temp != IntPtr.Zero && CloseHandle(temp)) closed++;
            else clean = false;
        }
        Emit("open_result", "\"event_open\":" + (ev != IntPtr.Zero ? "true" : "false") + ",\"iocp_open\":" + (iocp != IntPtr.Zero ? "true" : "false") + ",\"churn_closed\":" + closed);
        DebugBreak();
        clean = CloseAll(ref ev, ref iocp) && clean;
        Emit("close_result", "\"clean\":" + (clean ? "true" : "false"));
        DebugBreak();
        Emit("exit", "\"ok\":" + (clean ? "true" : "false") + ",\"reason\":\"cdb_htrace\"");
        return clean ? 0 : 1;
    }
}
