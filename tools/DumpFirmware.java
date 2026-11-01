import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileOptions;
import ghidra.program.model.listing.Function;
import java.io.PrintWriter;

public class DumpFirmware extends GhidraScript {
    public void run() throws Exception {
        String out=getScriptArgs()[0];
        DecompInterface dc=new DecompInterface();
        DecompileOptions options=new DecompileOptions();
        options.setRespectReadOnly(true);
        dc.setOptions(options);
        dc.openProgram(currentProgram);
        try(PrintWriter names=new PrintWriter(out+"_functions.txt");
            PrintWriter code=new PrintWriter(out+"_decompiled.c");
            PrintWriter refs=new PrintWriter(out+"_references.txt")) {
            for(Function f:currentProgram.getFunctionManager().getFunctions(true)) {
                names.println(f.getEntryPoint()+" "+f.getName()+" size="+f.getBody().getNumAddresses());
                if(f.isExternal() || f.isThunk()) continue;
                code.println("\n// "+f.getEntryPoint()+" "+f.getName());
                var result=dc.decompileFunction(f,15,monitor);
                if(result.decompileCompleted())code.println(result.getDecompiledFunction().getC());
                var ins=currentProgram.getListing().getInstructions(f.getBody(),true);
                while(ins.hasNext()) {
                    var i=ins.next();
                    for(var ref:i.getReferencesFrom())
                        if(ref.getToAddress().getOffset()>=0x20000000L)
                            refs.println(f.getEntryPoint()+" "+i.getAddress()+" -> "+ref.getToAddress()+" "+i);
                }
            }
        }
        dc.dispose();
    }
}
