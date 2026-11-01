import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import java.math.BigInteger;

public class SeedFirmware extends GhidraScript {
    public void run() throws Exception {
        var memory = currentProgram.getMemory();
        memory.getBlock(toAddr(0)).setWrite(false);
        if (memory.getBlock(toAddr(0x20000000L)) == null)
            memory.createUninitializedBlock("RAM",toAddr(0x20000000L),0x28000,false);
        if (memory.getBlock(toAddr(0x40000000L)) == null)
            memory.createUninitializedBlock("PERIPHERALS",toAddr(0x40000000L),0x100000,false);
        if (memory.getBlock(toAddr(0xe000e000L)) == null)
            memory.createUninitializedBlock("SYSTEM",toAddr(0xe000e000L),0x2000,false);
        memory.getBlock(toAddr(0x20000000L)).setWrite(true);
        for(long base:new long[]{0x40000000L,0xe000e000L}) {
            memory.getBlock(toAddr(base)).setWrite(true);
            memory.getBlock(toAddr(base)).setVolatile(true);
        }
        var tmode=currentProgram.getRegister("TMode");
        currentProgram.getProgramContext().setValue(tmode,toAddr(0),toAddr(0x7dfff),BigInteger.ONE);
        for(int i=1;i<112;i++) {
            long target=Integer.toUnsignedLong(memory.getInt(toAddr(i*4)));
            if((target&1)==1 && target>0x100 && target<0x20000) {
                Address a=toAddr(target&~1L);
                disassemble(a);
                if(getFunctionAt(a)==null) createFunction(a,i==1?"Reset_Handler":"Vector_"+i);
            }
        }
        disassemble(toAddr(0xe448));
        if(getFunctionAt(toAddr(0xe448))==null)createFunction(toAddr(0xe448),"is_isp_magic");
    }
}
