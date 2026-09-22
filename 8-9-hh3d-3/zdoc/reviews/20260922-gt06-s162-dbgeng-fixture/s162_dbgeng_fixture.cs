using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

internal static class S162DbgEngFixture
{
    private static readonly Guid IID_IDebugClient = new Guid("27fe5639-8407-4f47-8364-ee118fb08ac8");
    private static readonly Guid IID_IDebugControl = new Guid("5182e668-105e-416e-ad92-24ef800424ba");
    private const uint DEBUG_ATTACH_DEFAULT = 0;
    private const uint DEBUG_WAIT_DEFAULT = 0;
    private const uint DEBUG_EXECUTE_DEFAULT = 0;
    private const int S_OK = 0;
    private const int S_FALSE = 1;

    [DllImport("dbgeng.dll", CallingConvention = CallingConvention.StdCall)]
    private static extern int DebugCreate(ref Guid interfaceId, out IntPtr output);
    [DllImport("ole32.dll")]
    private static extern int CoInitializeEx(IntPtr reserved, uint coInit);
    [DllImport("ole32.dll")]
    private static extern void CoUninitialize();

    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    private delegate int QueryInterfaceDelegate(IntPtr self, ref Guid iid, out IntPtr result);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    private delegate int AttachProcessDelegate(IntPtr self, ulong server, uint pid, uint flags);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    private delegate int OpenLogFileDelegate(IntPtr self, [MarshalAs(UnmanagedType.LPStr)] string file, int append);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    private delegate int SetInterruptDelegate(IntPtr self, uint flags);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    private delegate int ExecuteDelegate(IntPtr self, uint outputControl, [MarshalAs(UnmanagedType.LPStr)] string command, uint flags);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    private delegate int WaitForEventDelegate(IntPtr self, uint flags, uint timeout);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    private delegate int DetachProcessesDelegate(IntPtr self);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    private delegate int EndSessionDelegate(IntPtr self, uint flags);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    private delegate int ReleaseDelegate(IntPtr self);

    private static IntPtr VTableEntry(IntPtr obj, int index)
    {
        IntPtr vtable = Marshal.ReadIntPtr(obj);
        return Marshal.ReadIntPtr(vtable, index * IntPtr.Size);
    }
    private static T Method<T>(IntPtr obj, int index) where T : class
    {
        return Marshal.GetDelegateForFunctionPointer(VTableEntry(obj, index), typeof(T)) as T;
    }
    private static string Hr(int hr) { return "0x" + ((uint)hr).ToString("X8"); }
    private static void Require(string op, int hr)
    {
        if (hr < 0) throw new InvalidOperationException(op + " failed " + Hr(hr));
    }
    private static string ReadReady(Process p, StringBuilder stdout)
    {
        string line1 = p.StandardOutput.ReadLine();
        string line2 = p.StandardOutput.ReadLine();
        stdout.AppendLine(line1 ?? "");
        stdout.AppendLine(line2 ?? "");
        if (line2 == null || !line2.Contains("\"kind\":\"ready\""))
            throw new InvalidOperationException("fixture did not emit ready: " + line2);
        return line2;
    }

    public static int Main(string[] args)
    {
        if (args.Length != 2) throw new ArgumentException("fixture.exe output_dir");
        string fixture = Path.GetFullPath(args[0]);
        string outputDir = Path.GetFullPath(args[1]);
        Directory.CreateDirectory(outputDir);
        string logPath = Path.Combine(outputDir, "dbgeng-output.log");
        string stdoutPath = Path.Combine(outputDir, "fixture-stdout.jsonl");
        var stdout = new StringBuilder();
        var psi = new ProcessStartInfo(fixture)
        {
            UseShellExecute = false,
            RedirectStandardInput = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true
        };
        using (Process target = Process.Start(psi))
        {
            if (target == null) throw new InvalidOperationException("fixture process did not start");
            ReadReady(target, stdout);
            uint pid = (uint)target.Id;
            IntPtr client = IntPtr.Zero;
            IntPtr control = IntPtr.Zero;
            bool comReady = false;
            int attachHr = -1;
            int initialWaitHr = -1;
            int attachWaitHr = -1;
            int interruptHr = -1;
            int runHr = -1;
            int finalWaitHr = -1;
            int exitCode = -1;
            try
            {
                int comHr = CoInitializeEx(IntPtr.Zero, 0x0);
                if (comHr < 0 && comHr != unchecked((int)0x80010106)) Require("CoInitializeEx", comHr);
                comReady = true;
                Guid clientIid = IID_IDebugClient;
                Require("DebugCreate", DebugCreate(ref clientIid, out client));
                var attach = Method<AttachProcessDelegate>(client, 12);
                attachHr = attach(client, 0, pid, DEBUG_ATTACH_DEFAULT);
                Require("AttachProcess", attachHr);
                var qi = Method<QueryInterfaceDelegate>(client, 0);
                Guid controlIid = IID_IDebugControl;
                Require("QueryInterface(IDebugControl)", qi(client, ref controlIid, out control));
                var openLog = Method<OpenLogFileDelegate>(control, 8);
                Require("OpenLogFile", openLog(control, logPath, 0));
                var wait = Method<WaitForEventDelegate>(control, 93);
                initialWaitHr = wait(control, DEBUG_WAIT_DEFAULT, 5000);
                Require("WaitForEvent(initial)", initialWaitHr);
                // AttachProcess is asynchronous; the first wait can report a
                // pending attach before a current process/thread exists.
                attachWaitHr = wait(control, DEBUG_WAIT_DEFAULT, 5000);
                if (attachWaitHr == S_FALSE)
                {
                    var interrupt = Method<SetInterruptDelegate>(control, 4);
                    interruptHr = interrupt(control, 0);
                    Require("SetInterrupt(active)", interruptHr);
                    attachWaitHr = wait(control, DEBUG_WAIT_DEFAULT, 5000);
                }
                Require("WaitForEvent(attach-complete)", attachWaitHr);
                var execute = Method<ExecuteDelegate>(control, 66);
                Require("reload", execute(control, 0, ".reload /f kernelbase.dll", DEBUG_EXECUTE_DEFAULT));
                Require("bp CreateEventW", execute(control, 0, "bp kernelbase!CreateEventW \".echo S162_CREATE_EVENT_ENTRY; gu; .echo S162_CREATE_EVENT_RETURN; ? @rax; g\"", DEBUG_EXECUTE_DEFAULT));
                Require("bp CreateIoCompletionPort", execute(control, 0, "bp kernelbase!CreateIoCompletionPort \".echo S162_CREATE_IOCP_ENTRY; gu; .echo S162_CREATE_IOCP_RETURN; ? @rax; g\"", DEBUG_EXECUTE_DEFAULT));
                Require("bp CloseHandle", execute(control, 0, "bp kernelbase!CloseHandle \".echo S162_CLOSE_ENTRY; ? @rcx; gu; .echo S162_CLOSE_RETURN; ? @rax; g\"", DEBUG_EXECUTE_DEFAULT));
                target.StandardInput.WriteLine("open");
                target.StandardInput.WriteLine("snapshot");
                target.StandardInput.WriteLine("churn 16");
                target.StandardInput.WriteLine("close_event");
                target.StandardInput.WriteLine("close_iocp");
                target.StandardInput.WriteLine("exit");
                target.StandardInput.Flush();
                runHr = execute(control, 0, "g", DEBUG_EXECUTE_DEFAULT);
                Thread.Sleep(250);
                for (int i = 0; i < 20 && !target.HasExited; i++)
                {
                    finalWaitHr = wait(control, DEBUG_WAIT_DEFAULT, 1000);
                    if (finalWaitHr < 0 && finalWaitHr != unchecked((int)0x8000000A)) break;
                }
                if (!target.HasExited) target.WaitForExit(5000);
                if (target.HasExited) exitCode = target.ExitCode;
            }
            finally
            {
                try
                {
                    if (client != IntPtr.Zero)
                    {
                        var detach = Method<DetachProcessesDelegate>(client, 25);
                        detach(client);
                        var end = Method<EndSessionDelegate>(client, 26);
                        end(client, 0);
                    }
                }
                catch { }
                if (control != IntPtr.Zero) { try { Method<ReleaseDelegate>(control, 2)(control); } catch { } }
                if (client != IntPtr.Zero) { try { Method<ReleaseDelegate>(client, 2)(client); } catch { } }
                if (comReady) CoUninitialize();
            }
            string err = target.StandardError.ReadToEnd();
            stdout.Append(target.StandardOutput.ReadToEnd());
            File.WriteAllText(stdoutPath, stdout.ToString(), new UTF8Encoding(false));
            File.WriteAllText(Path.Combine(outputDir, "run-summary.txt"),
                "pid=" + pid + Environment.NewLine +
                "attach_hr=" + Hr(attachHr) + Environment.NewLine +
                "initial_wait_hr=" + Hr(initialWaitHr) + Environment.NewLine +
                "attach_wait_hr=" + Hr(attachWaitHr) + Environment.NewLine +
                "interrupt_hr=" + Hr(interruptHr) + Environment.NewLine +
                "run_hr=" + Hr(runHr) + Environment.NewLine +
                "final_wait_hr=" + Hr(finalWaitHr) + Environment.NewLine +
                "actual_exit=" + exitCode + Environment.NewLine +
                "stderr_length=" + err.Length + Environment.NewLine,
                new UTF8Encoding(false));
            return exitCode == 0 ? 0 : 1;
        }
    }
}
