import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.program.model.listing.Function;
import java.io.PrintWriter;

public class DumpKeyboard extends GhidraScript {
    public void run() throws Exception {
        String out = getScriptArgs()[0];
        DecompInterface dc = new DecompInterface();
        dc.openProgram(currentProgram);
        try (PrintWriter names = new PrintWriter(out + "_functions.txt");
             PrintWriter code = new PrintWriter(out + "_decompiled.c")) {
            for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
                String n = f.getName(true);
                names.println(f.getEntryPoint() + " " + n);
                if (n.matches("(?i).*(StrokeCheckDlg|HID|Hid|SendCmd|ReadData|WriteData|Recv|USB|DeviceControl|KeyboardDevice|Feature|Report|Hall).*")
                    && !f.isExternal() && !f.isThunk()) {
                    code.println("\n// " + f.getEntryPoint() + " " + n);
                    var result = dc.decompileFunction(f, 30, monitor);
                    if (result.decompileCompleted()) code.println(result.getDecompiledFunction().getC());
                }
            }
        }
        dc.dispose();
    }
}
