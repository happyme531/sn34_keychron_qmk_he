# /// script
# dependencies = ["pefile", "pyelftools", "capstone"]
# ///
"""Package the complete source-built application in the existing OEM updater."""
import hashlib
import json
import argparse
from pathlib import Path
import struct
import pefile
from elftools.elf.elffile import ELFFile
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB
from capstone.arm_const import ARM_OP_IMM
from build_config import resolve_input
from storage import LAYOUT

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/"build/native_app"
BUILD=ROOT/"build/native_app_ota"

def main():
    global SOURCE,BUILD
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keychron-he",action="store_true",help="Package the independently tested Keychron HE build")
    parser.add_argument("--bat68",action="store_true",help="Package the production QMK platform after all required test groups pass")
    parser.add_argument("--build-dir",type=Path,help="Production build to package (requires --bat68)")
    parser.add_argument("--output-dir",type=Path,help="Package output directory")
    args=parser.parse_args()
    if args.keychron_he: SOURCE=ROOT/"build/keychron_he";BUILD=ROOT/"build/keychron_he_ota"
    if args.bat68: SOURCE=ROOT/"build/bat68";BUILD=ROOT/"build/sn34_ota"
    if args.build_dir:
        if not args.bat68:parser.error("--build-dir requires --bat68")
        SOURCE=(ROOT/args.build_dir).resolve()
        BUILD=SOURCE.with_name(SOURCE.name+"_ota")
    if args.output_dir:BUILD=(ROOT/args.output_dir).resolve()
    manifest=json.loads((SOURCE/"manifest.json").read_text())
    assert manifest["standalone"] and manifest["cold_initialization_included"] and manifest["qmk_keyboard_included"]
    assert manifest["rom_start"]=="0x0" and not manifest["original_application_inputs"] and not manifest["original_application_calls"]
    code=(SOURCE/"firmware.bin").read_bytes();app=(SOURCE/"application.bin").read_bytes()
    code_sha=hashlib.sha256(code).hexdigest();app_sha=hashlib.sha256(app).hexdigest()
    assert code_sha==manifest["image_sha256"] and app_sha==manifest["application_sha256"]
    assert len(app)==LAYOUT.app_size and app[:len(code)]==code and not any(app[len(code):LAYOUT.footer_address])
    assert int.from_bytes(app[LAYOUT.footer_address:LAYOUT.footer_address+4],"little")==LAYOUT.footer_magic
    tests=[]
    test_files=("test_results.json","he_test_results.json" if args.keychron_he else "keyboard_test_results.json","scan_test_results.json","boot_test_results.json")
    if args.keychron_he: test_files += ("eeprom_test_results.json",)
    if args.bat68:
        test_files=("platform_test_results.json","feature_test_results.json","usb_lighting_test_results.json",
            "storage_test_results.json","lifecycle_test_results.json","scan_test_results.json","boot_test_results.json","eeprom_test_results.json")
    for name in test_files:
        path=SOURCE/name;result=json.loads(path.read_text())
        assert result["status"]=="PASS_OFFLINE_NOT_FLASHED" and result["image_sha256"]==code_sha,name
        tests.append({"path":str(path.relative_to(ROOT)),"sha256":hashlib.sha256(path.read_bytes()).hexdigest()})
    for source in manifest["sources"]+manifest.get("build_inputs",[]):
        path=resolve_input(source["path"],manifest);assert hashlib.sha256(path.read_bytes()).hexdigest()==source["sha256"],str(path)
    with (SOURCE/"firmware.elf").open("rb") as stream:
        elf=ELFFile(stream);symbols=list(elf.get_section_by_name(".symtab").iter_symbols())
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB);md.detail=True
    functions=0;direct_branches=0
    for symbol in symbols:
        if symbol["st_info"]["type"]!="STT_FUNC" or not symbol["st_size"]:continue
        address=symbol["st_value"]&~1;size=symbol["st_size"]
        assert 0<=address<address+size<=len(code),(symbol.name,hex(address),size)
        functions+=1
        for instruction in md.disasm(code[address:address+size],address):
            mnemonic=instruction.mnemonic.split(".")[0]
            if mnemonic not in ("b","bl","beq","bne","bhs","blo","bcs","bcc","bmi","bpl","bvs","bvc","bhi","bls","bge","blt","bgt","ble","cbz","cbnz"):continue
            for operand in instruction.operands:
                if operand.type==ARM_OP_IMM:
                    assert 0<=operand.imm<len(code),(symbol.name,instruction.mnemonic,instruction.op_str)
                    direct_branches+=1
    assert functions>50 and direct_branches>100
    BUILD.mkdir(parents=True,exist_ok=True)
    wrapper=bytearray((ROOT/"analysis/oem_updater_v118.exe").read_bytes())
    pe=pefile.PE(data=bytes(wrapper))
    resources={item.id:item.directory.entries[0].data.struct for ty in pe.DIRECTORY_ENTRY_RESOURCE.entries if ty.id==10 for item in ty.directory.entries}
    assert resources[4000].Size==len(app)
    offset=pe.get_offset_from_rva(resources[4000].OffsetToData)
    assert hashlib.sha256(wrapper[offset:offset+len(app)]).hexdigest()=="38123b9677fd5aed94b7998b8cbed09a5ad139c7283d298752f0ae6ca5112a36"
    wrapper[offset:offset+len(app)]=app
    checksum=sum(struct.unpack(f"<{len(app)//2}H",app))&0xffff
    offset=pe.get_offset_from_rva(resources[4014].OffsetToData)
    wrapper[offset:offset+8]=f"{checksum:04X}".encode("utf-16le")
    pe=pefile.PE(data=bytes(wrapper))
    struct.pack_into("<I",wrapper,pe.OPTIONAL_HEADER.get_field_absolute_offset("CheckSum"),pe.generate_checksum())
    updater=BUILD/("SN34_QMK_HE_v2.exe" if args.bat68 else "SN34_QMK_NATIVE_v118.exe");updater.write_bytes(wrapper)
    (BUILD/"application.bin").write_bytes(app)
    pe=pefile.PE(data=bytes(wrapper));assert pe.verify_checksum()
    assert pe.get_data(resources[4000].OffsetToData,len(app))==app
    package={"status":"PASS_OFFLINE_NOT_FLASHED","implementation":"Complete source-built User application; original Bootloader is retained separately",
             "image_sha256":app_sha,"source_code_sha256":code_sha,"checksum":f"0x{checksum:04X}",
             "application_bytes":len(app),"code_bytes":len(code),"reset_vector":manifest["entry"],
             "source_manifest":str((SOURCE/"manifest.json").relative_to(ROOT)),"bringup_guard_enabled":manifest["bringup_guard_enabled"],
             "original_application_bytes_retained":0,"bootloader_bytes_in_package":0,
             "license_review":"analysis/sdk_license_review.json","limits":manifest["limits"]}
    if args.keychron_he or args.bat68: package.update(keychron_he=True,qmk_commit=manifest["qmk_commit"],qmk_repository=manifest["qmk_repository"])
    if args.bat68: package.update(qmk_platform=True,hardware_verified=False)
    verification={"status":"PASS_OFFLINE_NOT_FLASHED","image_sha256":app_sha,"updater_sha256":hashlib.sha256(wrapper).hexdigest(),
                  "tests":["Complete image contains source-linked code plus zero padding and the valid footer; no original application bytes are copied",
                           "Reset vectors, all sized function symbols and all immediate branch destinations are inside the source-linked image",
                           "Every recorded source and build input hash and all required ARM test artifact hashes match the packaged code",
                           "Original OEM updater contains the exact full application with matching firmware and PE checksums"],
                  "function_symbols_audited":functions,"direct_branches_audited":direct_branches,"source_tests":tests,
                  "limits":["Indirect calls are exercised by ARM tests; disassembly alone does not prove every possible runtime path", "Cold boot and OTA require hardware validation"]}
    (BUILD/"manifest.json").write_text(json.dumps(package,indent=2))
    (BUILD/"test_results.json").write_text(json.dumps(verification,indent=2))
    print(json.dumps({"package":package,"verification":verification},indent=2))

if __name__=="__main__":main()
