"""Model/serial selection must prevent commands reaching the wrong keyboard."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'util/sn34'))
import importlib
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch


class Device:
    def __init__(self):self.written=None
    def open_path(self,path):self.path=path
    def close(self):pass
    def set_nonblocking(self,value):pass
    def write(self,data):self.written=bytes(data);return len(data)
    def read(self,size,*args):
        if self.written is None:return []
        packet=self.written[1:]
        response=bytearray(size)
        response[:2]=bytes((0x55,packet[1]));response[5:8]=packet[5:8]
        self.written_once=self.written
        return list(response)


class HostSelection(unittest.TestCase):
    def setUp(self):
        self.device=Device()
        entries=[{'usage_page':0xff68,'serial_number':serial,'path':serial.encode(),'release_number':0x200,'product_string':'Test'}
                 for serial in ('ONE','TWO')]
        self.hid=SimpleNamespace(enumerate=Mock(return_value=entries),device=lambda:self.device)
        self.modules=patch.dict(sys.modules,{'hid':self.hid});self.modules.start();self.addCleanup(self.modules.stop)
        self.env=patch.dict('os.environ',{'SN34_KEYBOARD':'sn34_test','SN34_DEVICE_SERIAL':'TWO'})
        self.env.start();self.addCleanup(self.env.stop)
        import transport
        self.transport=importlib.reload(transport)

    def test_identity_and_serial_select_exactly_one_device(self):
        probe=self.transport.Probe()
        self.assertEqual(self.device.path,b'TWO')
        self.hid.enumerate.assert_called_once_with(0xfeed,0x34)
        probe.close()

    def test_ambiguous_devices_require_a_selection(self):
        with patch.dict('os.environ',{'SN34_DEVICE_SERIAL':''}):
            with self.assertRaisesRegex(RuntimeError,'select|Select'):
                self.transport.Probe()

    def test_diagnostic_tag_comes_from_the_selected_model(self):
        probe=self.transport.Probe()
        reply=probe.query(0x74)
        self.assertEqual(self.device.written_once[6:9],b'TST')
        self.assertEqual(reply[5:8],b'TST')


if __name__=='__main__':unittest.main()
