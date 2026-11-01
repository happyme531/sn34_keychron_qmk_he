import ghidra.app.script.GhidraScript;
import ghidra.program.model.symbol.SourceType;
public class RefineStock extends GhidraScript {
    public void run() throws Exception {
        currentProgram.getMemory().getBlock(toAddr(0)).setWrite(false);
        currentProgram.getMemory().getBlock(toAddr(0x20000000L)).setWrite(true);
        for(long base:new long[]{0x40000000L,0xe000e000L}) {
            var b=currentProgram.getMemory().getBlock(toAddr(base));
            b.setWrite(true);
            b.setVolatile(true);
        }
        long[] addresses={0x12844,0x760,0xe448,0xadc,0x1d8,0x5ad8,0x3e94,0x3a08,0x9d8,0xddb4,0x6ac4,0x6b28,0x2150};
        String[] names={"firmware_main","hall_scan_adc_irq","is_isp_magic","build_calibration_report","enter_boot_region_00200300","main_loop","select_hall_mux_phase","init_hall_adc","calibrate_adc_trim","process_hall_keys","hall_filter_update","hall_filter_init","hall_raw_to_travel"};
        for(int i=0;i<addresses.length;i++) {
            var f=getFunctionAt(toAddr(addresses[i]));
            if(f!=null)f.setName(names[i],SourceType.USER_DEFINED);
        }
    }
}
