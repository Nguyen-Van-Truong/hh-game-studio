using System;
using System.IO;
using System.Runtime.InteropServices;

// Bounded diagnostic continuation of S164. S164 proved WaitForEvent index 90
// is correct, but the engine had no selected current process. This harness
// enumerates the process list, selects the owned CreateProcess entry, and only
// then asks for its system id and installs the same bounded breakpoints.
internal static class S165DbgEngProcessSelection
{
    private static readonly Guid IID_IDebugClient = new Guid("27fe5639-8407-4f47-8364-ee118fb08ac8");
    private static readonly Guid IID_IDebugControl = new Guid("5182e668-105e-416e-ad92-24ef800424ba");
    private static readonly Guid IID_IDebugSystemObjects = new Guid("6b86fe2c-2c4f-4f0c-9da2-174311acc327");
    private const uint DEBUG_PROCESS = 1, DEBUG_WAIT_DEFAULT = 0, DEBUG_EXECUTE_DEFAULT = 0;
    [DllImport("dbgeng.dll", CallingConvention = CallingConvention.StdCall)] private static extern int DebugCreate(ref Guid iid, out IntPtr output);
    [DllImport("ole32.dll")] private static extern int CoInitializeEx(IntPtr reserved, uint coInit);
    [DllImport("ole32.dll")] private static extern void CoUninitialize();
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] private delegate int QueryInterfaceDelegate(IntPtr self, ref Guid iid, out IntPtr result);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] private delegate int CreateProcessDelegate(IntPtr self, ulong server, IntPtr commandLine, uint flags);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] private delegate int OpenLogFileDelegate(IntPtr self, [MarshalAs(UnmanagedType.LPStr)] string file, int append);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] private delegate int ExecuteDelegate(IntPtr self, uint outputControl, [MarshalAs(UnmanagedType.LPStr)] string command, uint flags);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] private delegate int WaitForEventDelegate(IntPtr self, uint flags, uint timeout);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] private delegate int GetNumberProcessesDelegate(IntPtr self, out uint number);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] private delegate int GetProcessIdsByIndexDelegate(IntPtr self, uint start, uint count, [Out] uint[] ids, [Out] uint[] sysIds);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] private delegate int SetCurrentProcessIdDelegate(IntPtr self, uint id);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] private delegate int GetCurrentProcessSystemIdDelegate(IntPtr self, out uint id);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] private delegate int GetExitCodeDelegate(IntPtr self, out uint code);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] private delegate int EndSessionDelegate(IntPtr self, uint flags);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] private delegate int ReleaseDelegate(IntPtr self);
    private static IntPtr V(IntPtr obj, int index) { return Marshal.ReadIntPtr(Marshal.ReadIntPtr(obj), index * IntPtr.Size); }
    private static T M<T>(IntPtr obj, int index) where T : class { return Marshal.GetDelegateForFunctionPointer(V(obj, index), typeof(T)) as T; }
    private static string Hr(int hr) { return "0x" + ((uint)hr).ToString("X8"); }
    private static void Need(string op, int hr) { if (hr < 0) throw new InvalidOperationException(op + " failed " + Hr(hr)); }
    public static int Main(string[] args)
    {
        if (args.Length != 3) throw new ArgumentException("fixture.exe output_dir command_file");
        string fixture = Path.GetFullPath(args[0]), dir = Path.GetFullPath(args[1]), commands = Path.GetFullPath(args[2]);
        Directory.CreateDirectory(dir);
        string log = Path.Combine(dir, "dbgeng-output.log"), summary = Path.Combine(dir, "run-summary.txt");
        string output = Path.Combine(dir, "fixture-output.jsonl"), gate = Path.Combine(dir, "debugger-gate.txt");
        File.Delete(gate); File.WriteAllText(commands, "open\nchurn 16\nclose\nexit\n");
        IntPtr client=IntPtr.Zero, control=IntPtr.Zero, systems=IntPtr.Zero, commandPtr=IntPtr.Zero; bool com=false;
        int createHr=-1, waitHr=-1, selectHr=-1, runHr=-1, finalWaitHr=-1, exitHr=-1; uint pid=0, exitCode=uint.MaxValue, count=0; uint[] ids=new uint[16], sysIds=new uint[16];
        try
        {
            int comHr=CoInitializeEx(IntPtr.Zero,0); if(comHr<0 && comHr!=unchecked((int)0x80010106)) Need("CoInitializeEx",comHr); com=true;
            Guid ciid=IID_IDebugClient; Need("DebugCreate",DebugCreate(ref ciid,out client));
            commandPtr=Marshal.StringToHGlobalAnsi("\""+fixture+"\" \""+output+"\" \""+commands+"\" \""+gate+"\"");
            createHr=M<CreateProcessDelegate>(client,13)(client,0,commandPtr,DEBUG_PROCESS); Need("CreateProcess",createHr);
            Guid ctlid=IID_IDebugControl; Need("QueryInterface(control)",M<QueryInterfaceDelegate>(client,0)(client,ref ctlid,out control));
            Need("OpenLogFile",M<OpenLogFileDelegate>(control,8)(control,log,0));
            waitHr=M<WaitForEventDelegate>(control,90)(control,DEBUG_WAIT_DEFAULT,10000); Need("WaitForEvent(initial)",waitHr);
            Guid siid=IID_IDebugSystemObjects; Need("QueryInterface(system)",M<QueryInterfaceDelegate>(client,0)(client,ref siid,out systems));
            Need("GetNumberProcesses",M<GetNumberProcessesDelegate>(systems,21)(systems,out count)); if(count==0) throw new InvalidOperationException("no debuggee process list");
            uint take=Math.Min(count,(uint)ids.Length); Need("GetProcessIdsByIndex",M<GetProcessIdsByIndexDelegate>(systems,22)(systems,0,take,ids,sysIds));
            selectHr=M<SetCurrentProcessIdDelegate>(systems,8)(systems,ids[0]); Need("SetCurrentProcessId",selectHr);
            Need("GetCurrentProcessSystemId",M<GetCurrentProcessSystemIdDelegate>(systems,27)(systems,out pid));
            var execute=M<ExecuteDelegate>(control,63);
            Need("reload",execute(control,0,".reload /f kernelbase.dll",DEBUG_EXECUTE_DEFAULT));
            Need("bp CreateEventW",execute(control,0,"bp kernelbase!CreateEventW \".echo S165_CREATE_EVENT_ENTRY; gu; .echo S165_CREATE_EVENT_RETURN; ? @rax; g\"",DEBUG_EXECUTE_DEFAULT));
            Need("bp CreateIoCompletionPort",execute(control,0,"bp kernelbase!CreateIoCompletionPort \".echo S165_CREATE_IOCP_ENTRY; gu; .echo S165_CREATE_IOCP_RETURN; ? @rax; g\"",DEBUG_EXECUTE_DEFAULT));
            Need("bp CloseHandle",execute(control,0,"bp kernelbase!CloseHandle \".echo S165_CLOSE_ENTRY; ? @rcx; gu; .echo S165_CLOSE_RETURN; ? @rax; g\"",DEBUG_EXECUTE_DEFAULT));
            File.WriteAllText(gate,"go\n"); runHr=execute(control,0,"g",DEBUG_EXECUTE_DEFAULT);
            for(int i=0;i<15;i++){finalWaitHr=M<WaitForEventDelegate>(control,90)(control,DEBUG_WAIT_DEFAULT,1000); if(finalWaitHr<0)break;}
            exitHr=M<GetExitCodeDelegate>(client,27)(client,out exitCode);
            File.WriteAllText(summary,"create_hr="+Hr(createHr)+Environment.NewLine+"wait_hr="+Hr(waitHr)+Environment.NewLine+"process_count="+count+Environment.NewLine+"debugger_ids="+string.Join(",",ids,0,(int)Math.Min(count,(uint)ids.Length))+Environment.NewLine+"system_ids="+string.Join(",",sysIds,0,(int)Math.Min(count,(uint)sysIds.Length))+Environment.NewLine+"select_hr="+Hr(selectHr)+Environment.NewLine+"pid="+pid+Environment.NewLine+"run_hr="+Hr(runHr)+Environment.NewLine+"final_wait_hr="+Hr(finalWaitHr)+Environment.NewLine+"exit_hr="+Hr(exitHr)+Environment.NewLine+"debugger_exit_code="+exitCode+Environment.NewLine);
            return 0;
        }
        catch(Exception ex){File.WriteAllText(summary,"exception="+ex.GetType().FullName+Environment.NewLine+"message="+ex.Message+Environment.NewLine+"create_hr="+Hr(createHr)+Environment.NewLine+"wait_hr="+Hr(waitHr)+Environment.NewLine+"process_count="+count+Environment.NewLine+"select_hr="+Hr(selectHr)+Environment.NewLine+"pid="+pid+Environment.NewLine);return 1;}
        finally{try{if(client!=IntPtr.Zero)M<EndSessionDelegate>(client,26)(client,0);}catch{} try{if(systems!=IntPtr.Zero)M<ReleaseDelegate>(systems,2)(systems);}catch{} try{if(control!=IntPtr.Zero)M<ReleaseDelegate>(control,2)(control);}catch{} try{if(client!=IntPtr.Zero)M<ReleaseDelegate>(client,2)(client);}catch{} if(commandPtr!=IntPtr.Zero)Marshal.FreeHGlobal(commandPtr);if(com)CoUninitialize();}
    }
}
