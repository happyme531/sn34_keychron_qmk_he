import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileOptions;
import ghidra.program.model.listing.Function;
import java.io.PrintWriter;
import java.util.TreeSet;

public class InspectUpdater extends GhidraScript {
    public void run() throws Exception {
        currentProgram.getMemory().getBlock(toAddr(0x400000)).setWrite(false);
        var functions=new TreeSet<Function>((a,b)->a.getEntryPoint().compareTo(b.getEntryPoint()));
        var symbols=currentProgram.getSymbolTable().getAllSymbols(true);
        while(symbols.hasNext()) {
            var s=symbols.next();
            if(s.getName().matches(".*(HidD_SetFeature|HidD_GetFeature|FindResourceW|LoadResource|WriteFile|ReadFile).*")) {
                for(var ref:getReferencesTo(s.getAddress())) {
                    Function f=getFunctionContaining(ref.getFromAddress());
                    if(f!=null)functions.add(f);
                }
            }
        }
        // Include callers: wrappers commonly hide the interesting protocol body.
        for(int level=0;level<2;level++) {
            var copy=new java.util.ArrayList<Function>(functions);
            for(Function f:copy)for(var ref:getReferencesTo(f.getEntryPoint())) {
                Function caller=getFunctionContaining(ref.getFromAddress());
                if(caller!=null)functions.add(caller);
            }
        }
        DecompInterface dc=new DecompInterface();
        DecompileOptions opts=new DecompileOptions();opts.setRespectReadOnly(true);dc.setOptions(opts);
        dc.openProgram(currentProgram);
        try(PrintWriter out=new PrintWriter(getScriptArgs()[0])) {
            for(Function f:functions) {
                out.println("\n// "+f.getEntryPoint()+" "+f.getName());
                var result=dc.decompileFunction(f,20,monitor);
                if(result.decompileCompleted())out.println(result.getDecompiledFunction().getC());
            }
        }
        dc.dispose();
    }
}
