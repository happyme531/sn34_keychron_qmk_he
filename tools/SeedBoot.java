import ghidra.app.script.GhidraScript;
import java.math.BigInteger;
public class SeedBoot extends GhidraScript {
    public void run() throws Exception {
        var m=currentProgram.getMemory();
        m.getBlock(toAddr(0)).setWrite(false);
        var physical=m.createByteMappedBlock("BOOT_PHYSICAL",toAddr(0x00200000L),toAddr(0),0x2000,false);
        physical.setWrite(false);
        var ram=m.createUninitializedBlock("RAM",toAddr(0x20000000L),0x28000,false);ram.setWrite(true);
        for(long base:new long[]{0x40000000L,0xe000e000L,0x00600000L}) {
            var b=m.createUninitializedBlock("MMIO_"+Long.toHexString(base),toAddr(base),
                    base==0x40000000L?0x100000:0x2000,false);
            b.setWrite(true);b.setVolatile(true);
        }
        var t=currentProgram.getRegister("TMode");
        currentProgram.getProgramContext().setValue(t,toAddr(0),toAddr(0x1fff),BigInteger.ONE);
        for(int i=1;i<112;i++) {
            long v=Integer.toUnsignedLong(m.getInt(toAddr(i*4)));
            if((v&1)==1 && v>0x100 && v<0x2000) {
                var a=toAddr(v&~1L);disassemble(a);
                if(getFunctionAt(a)==null)createFunction(a,i==1?"Reset_Handler":"Vector_"+i);
            }
        }
        for(long at:new long[]{0x1c0,0x300}) {
            var a=toAddr(at);disassemble(a);
            if(getFunctionAt(a)==null)createFunction(a,at==0x300?"enter_usb_isp_from_app":"scatter_start");
        }
    }
}
