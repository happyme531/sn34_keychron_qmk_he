import ghidra.app.script.GhidraScript;
import java.math.BigInteger;
public class SeedPartialFirmware extends GhidraScript {
    public void run() throws Exception {
        var m=currentProgram.getMemory();
        m.getBlock(toAddr(0x9200)).setWrite(false);
        m.createUninitializedBlock("UNKNOWN_LOW_ROM",toAddr(0),0x9200,false);
        m.getBlock(toAddr(0)).setWrite(false);
        m.createUninitializedBlock("RAM",toAddr(0x20000000L),0x28000,false);
        for(long base:new long[]{0x40000000L,0xe000e000L}) {
            var b=m.createUninitializedBlock("MMIO_"+Long.toHexString(base),toAddr(base),base==0x40000000L?0x100000:0x2000,false);
            b.setWrite(true);b.setVolatile(true);
        }
        var t=currentProgram.getRegister("TMode");
        currentProgram.getProgramContext().setValue(t,toAddr(0),toAddr(0x191ff),BigInteger.ONE);
        for(long at=0xb800;at<0x16300;at+=2) {
            int v=Short.toUnsignedInt(m.getShort(toAddr(at)));
            if((v&0xff00)==0xb500 || v==0xe92d || at==0xf488) {
                var a=toAddr(at);
                if(getFunctionContaining(a)==null) {
                    disassemble(a);
                    if(getFunctionAt(a)==null)createFunction(a,at==0xf488?"is_isp_magic":null);
                }
            }
        }
    }
}
