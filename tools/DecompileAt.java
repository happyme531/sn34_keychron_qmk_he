import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.program.model.listing.Function;
import java.io.PrintWriter;
import java.util.TreeSet;
public class DecompileAt extends GhidraScript {
    public void run() throws Exception {
        String[] args=getScriptArgs();
        var fs=new TreeSet<Function>((a,b)->a.getEntryPoint().compareTo(b.getEntryPoint()));
        try(PrintWriter out=new PrintWriter(args[0])) {
            for(int i=1;i<args.length;i++) {
                if(args[i].startsWith("refs:")) {
                    var a=toAddr(Long.parseUnsignedLong(args[i].substring(5),16));
                    for(var r:getReferencesTo(a)) {
                        out.println("// REF "+r.getFromAddress()+" "+r.getReferenceType()+" -> "+a);
                        Function f=getFunctionContaining(r.getFromAddress());if(f!=null)fs.add(f);
                    }
                } else {
                    Function f=getFunctionContaining(toAddr(Long.parseUnsignedLong(args[i],16)));if(f!=null)fs.add(f);
                }
            }
            DecompInterface dc=new DecompInterface();dc.openProgram(currentProgram);
            for(Function f:fs) {
                out.println("\n// "+f.getEntryPoint()+" "+f.getName());
                var r=dc.decompileFunction(f,30,monitor);
                if(r.decompileCompleted())out.println(r.getDecompiledFunction().getC());
            }
            dc.dispose();
        }
    }
}
