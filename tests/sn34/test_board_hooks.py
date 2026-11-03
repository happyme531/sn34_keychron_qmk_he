"""Exercise board/user callback ownership through the real QMK event loop."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent / 'common'))
from keyboard import Keyboard, KEYS
from emulator import FIRMWARE, SYMS
from model import load_board
from target import keyboard_name
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_PC, UC_ARM_REG_LR


class UserHooks(Keyboard):
    def __init__(self):
        self.record_allowed = self.rgb_allowed = True
        self.record_callbacks = []
        self.indicator_callbacks = []
        self.task_calls = self.user_task_calls = 0
        super().__init__()

    def on_code(self, u, address, size, data):
        # Supply user responses and observe the public HE calls. The board
        # wrappers, event dispatch and common housekeeping body still execute.
        result = None
        if address == (SYMS['process_record_user'] & ~1):
            self.record_callbacks.append('user')
            result = self.record_allowed
        elif address == (SYMS['process_record_profile'] & ~1):
            self.record_callbacks.append('profile')
            result = True
        elif address == (SYMS.get('rgb_matrix_indicators_user', 1) & ~1):
            self.indicator_callbacks.append('user')
            result = self.rgb_allowed
        elif address == (SYMS.get('analog_matrix_indicator', 1) & ~1):
            self.indicator_callbacks.append('he')
            result = 0
        elif address == (SYMS['housekeeping_task_user'] & ~1):
            self.user_task_calls += 1
            result = 0
        elif address == (SYMS['sn34_he_task'] & ~1):
            self.task_calls += 1
        if result is not None:
            u.reg_write(UC_ARM_REG_R0, int(result))
            u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
            return
        super().on_code(u, address, size, data)


class BoardHooks(unittest.TestCase):
    def test_user_can_veto_press_and_release_before_profile_processing(self):
        m = UserHooks()
        key = next(key for key in KEYS if key['raw_slot'] != load_board()['roles']['fn'])
        m.call('dynamic_keymap_set_keycode', 0, *key['matrix'], 4)
        m.record_callbacks.clear()
        m.record_allowed = False
        for travel in (140, 0):
            m.travel_key(key, travel)
            m.step()
        self.assertEqual(m.record_callbacks, ['user', 'user'])
        self.assertFalse(m.pressed(4))
        m.record_callbacks.clear()
        m.record_allowed = True
        m.travel_key(key, 140)
        m.step()
        self.assertTrue(m.pressed(4))
        m.travel_key(key, 0)
        m.step()
        self.assertFalse(m.pressed(4))
        self.assertEqual(m.record_callbacks, ['user', 'profile', 'user', 'profile'])

    @unittest.skipUnless(FIRMWARE.features['rgb'], 'RGB disabled')
    def test_user_can_veto_he_indicators(self):
        m = UserHooks()
        for allowed, callbacks in ((False, ['user']), (True, ['user', 'he'])):
            m.indicator_callbacks.clear()
            m.rgb_allowed = allowed
            self.assertEqual(m.call('rgb_matrix_indicators_kb'), int(allowed))
            self.assertEqual(m.indicator_callbacks, callbacks)

    def test_common_task_and_user_housekeeping_each_run_once(self):
        m = UserHooks()
        before = m.task_calls, m.user_task_calls
        m.step()
        self.assertEqual((m.task_calls, m.user_task_calls), (before[0] + 1, before[1] + 1))

    @unittest.skipUnless(keyboard_name() == 'battle68', 'Battle68 Win-lock/OS shortcuts')
    def test_user_can_veto_board_shortcuts(self):
        m = UserHooks()
        key = next(key for key in KEYS if key['raw_slot'] != load_board()['roles']['fn'])
        def settings():
            return tuple(bytes(m.u.mem_read(SYMS[name], FIRMWARE.symbols[name]['st_size']))
                         for name in ('keymap_config', 'default_layer_state'))
        before = settings()
        m.record_allowed = False
        for code in (0x7e1e, 0x7e1f):
            m.call('dynamic_keymap_set_keycode', 0, *key['matrix'], code)
            for travel in (140, 0):
                m.travel_key(key, travel)
                m.step()
            self.assertEqual(settings(), before)

    @unittest.skipUnless(keyboard_name() == 'langtu/boom68/wired', 'BOOM68 consumed chord policy')
    def test_user_veto_does_not_leave_a_consumed_release_pending(self):
        m = UserHooks()
        m.press('Fn')
        m.press('P')
        before = len(m.record_callbacks)
        m.record_allowed = False
        m.release('P')
        self.assertEqual(m.record_callbacks[before:], ['user'])
        m.record_allowed = True
        m.release('Fn')
        m.press('P')
        self.assertTrue(m.pressed(0x13))
        m.release('P')
        self.assertFalse(m.pressed(0x13))


if __name__ == '__main__':
    unittest.main()
