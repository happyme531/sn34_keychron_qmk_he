"""Record board-facing lighting parameters; does not copy original routines."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
image=(ROOT/"analysis/v118_rcdata_4000.bin").read_bytes()
assert hashlib.sha256(image).hexdigest()=="38123b9677fd5aed94b7998b8cbed09a5ad139c7283d298752f0ae6ca5112a36"
pair_codes=list(image[0x14504:0x14508])
order=list(image[0x1461c:0x1461c+67])
assert pair_codes==[0x88,0x8e,0xe8,0xee]
assert sorted(order)==list(range(67))
data={
    "status":"ORIGINAL_FIRMWARE_PARAMETERS_NOT_YET_LIGHTING_HARDWARE_VERIFIED",
    "indicators":{"capslock":"P1.6","win_lock":"P1.10","mac_mode":"P1.11","active_level_in_original_gpio":"high"},
    "ws2812":{
        "spi":"SPI1","data_pin_candidate":"P1.15","clock_pin_configured":"P1.13","enable_pin_candidate":"P1.4",
        "data_register":"0x4002b018","dma":"DMA1 channel 0","dma_irq":56,
        "original_spi_ctrl0":"0x81008","original_spi_ctrl1":"0x7001f",
        "data_bits":8,"sclkdiv_register":31,"clock_source":"HCLK",
        "expected_spi_hz_at_hclk_192mhz":3000000,
        "expected_led_bit_hz":750000,
        "encoding":{"zero_bits":"1000","one_bits":"1110","two_bit_lookup":pair_codes},
        "wire_color_order":"G,R,B according to original encoder argument order",
        "original_dma_bytes":805,"leading_zero_bytes":1,"encoded_bytes_per_pixel":12,
        "pixels_transmitted_in_original_frame":67,"color_plane_capacity":90,
        "layout_order_table_candidate":order,
        "facts_sources":{"encoder":"original function 0x6e68","dma_start":"original function 0x8cac","spi_setup":"original function 0xf528","dma_setup":"original function 0x1040"},
        "limits":["Actual LED count, data-pin continuity, color order and chain order still require physical confirmation", "Clock rates are inferred from register configuration; no scope measurement", "The 67-entry order table is a candidate physical-layout mapping, not yet correlated to each key"]
    }
}
(ROOT/"analysis/lighting_board_profile.json").write_text(json.dumps(data,indent=2))
print(json.dumps(data,indent=2))
