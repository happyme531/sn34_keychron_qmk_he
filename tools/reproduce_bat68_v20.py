# /// script
# dependencies = ["pyelftools"]
# ///
"""Reproduce the exact installed v20 image for recovery debugging only."""
import hashlib
import shutil
import build_bat68 as builder

out=builder.ROOT/"build/bat68_v20_repro"
source=out/"source"
shutil.copytree(builder.SRC,source,dirs_exist_ok=True)
config=(source/"config.h").read_text()
config=config.replace("#define RGB_MATRIX_DEFAULT_ON true","#define RGB_MATRIX_DEFAULT_ON false")
config=config.replace("#define RGB_MATRIX_DEFAULT_MODE RGB_MATRIX_SOLID_COLOR\n","")
(source/"config.h").write_text(config)
protocol=(source/"protocol.c").read_text()
start=protocol.index("static const uint8_t ota_report[]=")
end=protocol.index(";",start)+1
protocol=protocol[:start]+'''static const uint8_t ota_report[]={0x06,0x67,0xff,0x09,0x61,0xa1,1,0x09,0x63,0x15,0,0x26,0xff,0,
    0x75,8,0x96,0,0x10,0x91,2,0x09,0x62,0x95,64,0xb1,2,0xc0};'''+protocol[end:]
protocol=protocol.replace("{.feature_report_length=64,\n         .report_desc_length=sizeof(ota_report),.report_desc=(uint8_t*)ota_report}",
    "{.bOutEp=1,.OutEpNum=4,.out_report_length=64,.feature_report_length=64,\n         .report_desc_length=sizeof(ota_report),.report_desc=(uint8_t*)ota_report,.hs_Interval=4}")
(source/"protocol.c").write_text(protocol)
builder.SRC=source;builder.BUILD=out
builder.main()
expected="cd8f0e26dcfdd2e78eafff21410e67eca3a041022d37059c73472957d403b049"
actual=hashlib.sha256((out/"native_usb.bin").read_bytes()).hexdigest()
assert actual==expected,("Reproduction differs; do not use guessed addresses",actual,expected)
print("EXACT_V20_IMAGE_REPRODUCED")
