using System;
using System.ComponentModel;
using System.Runtime.InteropServices;

internal static class NativeFixtureS160
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

    private static string Hex(IntPtr value)
    {
        return "0x" + value.ToInt64().ToString("X");
    }

    private static void Emit(string kind, string body)
    {
        Console.WriteLine("{\"kind\":\"" + kind + "\"," + body + "}");
        Console.Out.Flush();
    }

    private static IntPtr OpenEvent(string label)
    {
        IntPtr handle = CreateEventW(IntPtr.Zero, true, false, null);
        if (handle == IntPtr.Zero)
        {
            Emit("error", "\"operation\":\"" + label + "\",\"win32_error\":" + Marshal.GetLastWin32Error());
            return IntPtr.Zero;
        }
        Emit("open", "\"type\":\"Event\",\"label\":\"" + label + "\",\"handle\":\"" + Hex(handle) + "\"");
        return handle;
    }

    private static IntPtr OpenCompletion()
    {
        IntPtr handle = CreateIoCompletionPort(InvalidHandleValue, IntPtr.Zero, UIntPtr.Zero, 1);
        if (handle == IntPtr.Zero)
        {
            Emit("error", "\"operation\":\"CreateIoCompletionPort\",\"win32_error\":" + Marshal.GetLastWin32Error());
            return IntPtr.Zero;
        }
        Emit("open", "\"type\":\"IoCompletion\",\"label\":\"primary\",\"handle\":\"" + Hex(handle) + "\"");
        return handle;
    }

    private static void Close(string type, ref IntPtr handle)
    {
        if (handle == IntPtr.Zero)
        {
            Emit("close", "\"type\":\"" + type + "\",\"state\":\"already_closed\"");
            return;
        }
        IntPtr old = handle;
        bool ok = CloseHandle(handle);
        handle = IntPtr.Zero;
        string errorText = ok ? "0" : Marshal.GetLastWin32Error().ToString();
        Emit("close", "\"type\":\"" + type + "\",\"handle\":\"" + Hex(old) + "\",\"ok\":" + (ok ? "true" : "false") + ",\"win32_error\":" + errorText);
    }

    public static int Main()
    {
        Emit("start", "\"pid\":" + GetCurrentProcessId() + ",\"fixture\":\"s160-native-handle-lifecycle\"");
        IntPtr eventHandle = OpenEvent("primary");
        IntPtr completionHandle = OpenCompletion();
        string command;
        while ((command = Console.ReadLine()) != null)
        {
            command = command.Trim();
            if (command.Equals("snapshot", StringComparison.OrdinalIgnoreCase))
            {
                Emit("snapshot", "\"event_open\":" + (eventHandle != IntPtr.Zero ? "true" : "false") + ",\"iocp_open\":" + (completionHandle != IntPtr.Zero ? "true" : "false"));
            }
            else if (command.Equals("close_event", StringComparison.OrdinalIgnoreCase))
            {
                Close("Event", ref eventHandle);
            }
            else if (command.Equals("close_iocp", StringComparison.OrdinalIgnoreCase))
            {
                Close("IoCompletion", ref completionHandle);
            }
            else if (command.StartsWith("churn ", StringComparison.OrdinalIgnoreCase))
            {
                int count;
                if (!int.TryParse(command.Substring(6), out count) || count < 0 || count > 1024)
                {
                    Emit("error", "\"operation\":\"churn\",\"message\":\"invalid_count\"");
                    continue;
                }
                int closed = 0;
                for (int i = 0; i < count; i++)
                {
                    IntPtr h = CreateEventW(IntPtr.Zero, true, false, null);
                    if (h != IntPtr.Zero && CloseHandle(h)) closed++;
                }
                Emit("churn", "\"requested\":" + count + ",\"closed\":" + closed);
            }
            else if (command.Equals("exit", StringComparison.OrdinalIgnoreCase))
            {
                Close("Event", ref eventHandle);
                Close("IoCompletion", ref completionHandle);
                Emit("exit", "\"ok\":true");
                return 0;
            }
            else
            {
                Emit("error", "\"operation\":\"command\",\"message\":\"unknown\"");
            }
        }
        Close("Event", ref eventHandle);
        Close("IoCompletion", ref completionHandle);
        Emit("exit", "\"ok\":true,\"reason\":\"stdin_eof\"");
        return 0;
    }
}
