# /// script
# dependencies = ["unicorn", "pyelftools", "capstone"]
# ///
"""Execute a separate minimal keymap to check board/user hook ownership."""
import hashlib
import json
from test_bat68 import Keyboard, BUILD, IMAGE, SYMS


def main():
    manifest=json.loads((BUILD/"manifest.json").read_text(encoding="utf-8"))
    assert manifest["keymap"]=="minimal", "Build --keymap minimal and set BAT68_NATIVE_BUILD to its output"
    m=Keyboard()
    counter=lambda name:int.from_bytes(m.u.mem_read(SYMS[name],4),"little")
    assert counter("bat68_test_matrix_inits")==1
    before=counter("bat68_test_matrix_scans");m.step()
    assert counter("bat68_test_matrix_scans")==before+1
    m.press("Esc");assert m.pressed(0xe3);m.release("Esc")
    assert counter("bat68_test_user_events")>=2
    m.press("A");m.release("A")
    m.press("Esc");assert not m.pressed(0xe3);m.release("Esc")
    m.press("S");m.release("S")
    assert m.raw_command(bytes((0xa3,)))[1]==2
    m.press("D");m.release("D")
    assert m.raw_command(bytes((0xa9,0x10)))[2]==1
    m.call("bat68_eeprom_save")
    loaded=Keyboard(bytes(m.u.mem_read(0x79000,0x5000)))
    assert loaded.raw_command(bytes((0xa3,)))[1]==2
    loaded.press("Esc");assert not loaded.pressed(0xe3);loaded.release("Esc")
    assert loaded.raw_command(bytes((0xa9,0x10)))[2]==1
    result={"status":"PASS_OFFLINE_NOT_FLASHED","image_sha256":hashlib.sha256(IMAGE).hexdigest(),
            "tests":["A separate minimal keymap retains Win Lock, OS switching and profile keycodes without default-keymap inclusion",
                     "Ordinary keys reach process_record_user; upstream matrix init and scan hooks run exactly once",
                     "The minimal keymap's board settings restore from the same persistent format"]}
    (BUILD/"board_hooks_test_results.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2))


if __name__=="__main__":main()
