using System;
using System.IO;
using System.Runtime.InteropServices;

internal static class NativeFixtureS163
{
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern IntPtr CreateEventW(IntPtr attributes, bool manualReset, bool initialState, string name);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr CreateIoCompletionPort(IntPtr fileHandle, IntPtr existingPort, UIntPtr completionKey, uint threads);
    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CloseHandle(IntPtr handle);
    [DllImport("kernel32.dll")]
    private static extern uint GetCurrentProcessId();
    private static IntPtr ev;
    private static IntPtr iocp;
    private static bool clean = true;
    private static void Emit(string kind, string body) { Console.WriteLine("{\"kind\":\"" + kind + "\"," + body + "}"); Console.Out.Flush(); }
    private static string Hex(IntPtr value) { return "0x" + value.ToInt64().ToString("X"); }
    private static bool CloseOne(string type, ref IntPtr handle) {
        if (handle == IntPtr.Zero) return true;
        IntPtr old = handle; bool ok = CloseHandle(handle); handle = IntPtr.Zero;
        Emit("close", "\"type\":\"" + type + "\",\"handle\":\"" + Hex(old) + "\",\"ok\":" + (ok ? "true" : "false"));
        return ok;
    }
    private static void Do(string command) {
        command = command.Trim();
        if (command.Equals("open", StringComparison.OrdinalIgnoreCase)) {
            ev = CreateEventW(IntPtr.Zero, true, false, null);
            iocp = CreateIoCompletionPort(new IntPtr(-1), IntPtr.Zero, UIntPtr.Zero, 1);
            bool ok = ev != IntPtr.Zero && iocp != IntPtr.Zero; clean = clean && ok;
            Emit("open", "\"event\":\"" + Hex(ev) + "\",\"iocp\":\"" + Hex(iocp) + "\",\"ok\":" + (ok ? "true" : "false"));
        } else if (command.StartsWith("churn ", StringComparison.OrdinalIgnoreCase)) {
            int n; if (!int.TryParse(command.Substring(6), out n) || n < 0 || n > 8192) { clean = false; Emit("error", "\"operation\":\"churn\""); return; }
            int closed = 0; for (int i = 0; i < n; i++) { IntPtr h = CreateEventW(IntPtr.Zero, true, false, null); if (h != IntPtr.Zero && CloseHandle(h)) closed++; }
            clean = clean && closed == n; Emit("churn", "\"requested\":" + n + ",\"closed\":" + closed);
        } else if (command.Equals("close", StringComparison.OrdinalIgnoreCase)) {
            clean = CloseOne("Event", ref ev) && clean; clean = CloseOne("IoCompletion", ref iocp) && clean;
        } else if (command.Equals("exit", StringComparison.OrdinalIgnoreCase)) {
            clean = CloseOne("Event", ref ev) && clean; clean = CloseOne("IoCompletion", ref iocp) && clean;
            Emit("exit", "\"ok\":" + (clean ? "true" : "false") + ",\"actual_exit\":" + (clean ? "0" : "1")); Environment.Exit(clean ? 0 : 1);
        } else { clean = false; Emit("error", "\"operation\":\"command\",\"message\":\"unknown\""); }
    }
    public static int Main(string[] args) {
        if (args.Length != 3) return 2;
        using (var writer = new StreamWriter(args[0], false)) {
            writer.AutoFlush = true; Console.SetOut(writer);
            Emit("start", "\"pid\":" + GetCurrentProcessId() + ",\"fixture\":\"s163-dbgeng-createprocess\"");
            Emit("ready", "\"pid\":" + GetCurrentProcessId() + ",\"observer_attach_before_open\":true");
            for (int i = 0; i < 300 && !File.Exists(args[2]); i++) System.Threading.Thread.Sleep(10);
            if (!File.Exists(args[2])) { Emit("error", "\"operation\":\"debugger_gate\",\"message\":\"timeout\""); return 3; }
            foreach (string command in File.ReadAllLines(args[1])) Do(command);
            clean = CloseOne("Event", ref ev) && clean; clean = CloseOne("IoCompletion", ref iocp) && clean;
            Emit("exit", "\"ok\":" + (clean ? "true" : "false") + ",\"actual_exit\":" + (clean ? "0" : "1") + ",\"reason\":\"eof\"");
            return clean ? 0 : 1;
        }
    }
}
