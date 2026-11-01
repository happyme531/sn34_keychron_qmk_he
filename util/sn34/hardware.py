"""Compile target wiring into inline operations for the interrupt hot path."""
from build_config import write_if_changed


def number(value):
    return int(value, 0) if isinstance(value, str) else value


def gpio(pin, on):
    port, bit = pin
    if not 0 <= port <= 3 or not 0 <= bit <= 20:
        raise ValueError(f'Invalid SN34 GPIO: {pin}')
    return f'SN_GPIO{port}->{"BSET" if on else "BCLR"}=1u<<{bit};'


def generate_hardware(board, build, rgb_enabled=True):
    hardware, scan = board['hardware'], board['scan']
    config = '#pragma once\n'
    config += f'#define HAL_EHS_FREQ_MHZ {hardware["crystal_mhz"]}\n'
    config += f'#define SN34_PLL_NS {hardware["pll_ns"]}\n#define SN34_PLL_FS RCC_PLL_DIV{hardware["pll_fs_div"]}\n'
    rgb=hardware.get('rgb') if rgb_enabled else None
    if rgb_enabled and rgb is None:
        raise ValueError('RGB is enabled but the target has no RGB hardware backend')
    if rgb is not None and (rgb['spi']!=1 or rgb['dma_channel']!=0):
        raise ValueError('The current WS2812 backend supports SPI1 / DMA1 channel 0; select or implement a different backend for other routing')
    if rgb is not None:config += f'#define SN34_RGB_SPI_DIVIDER {rgb["divider"]}\n'
    for name in ('adc_pre_clock', 'power_en_time', 'hold_time', 'xtest'):
        config += f'#define SN34_{name.upper()} {scan[name]}\n'
    write_if_changed(build / 'hardware_config.generated.h', config)
    code = '#pragma once\n#include "ll_gpio_afio.h"\n'
    code += 'static inline void sn34_board_gpio_init(void){\n'
    for port in range(4):
        code += f'__HAL_RCC_GPIO_P{port}_CLK_ENABLE();\n'
        code += f'SN_GPIO{port}->DATAOUT={number(hardware["gpio_output"][port])}u;\n'
        code += f'SN_GPIO{port}->PUTYPE=0x1fffffu;\n'
        # Preserve the validated startup order: output value, pulls, direction.
        code += f'SN_GPIO{port}->PULLEN={number(hardware["gpio_pull"][port])}u;\n'
        code += f'SN_GPIO{port}->DIR={number(hardware["gpio_direction"][port])}u;\n'
    for port, registers in enumerate(hardware['gpio_afio']):
        for index, value in enumerate(registers):
            code += f'SN_ALWAYSON->P{port}_AFIO{index}={number(value)}u;\n'
    code += '}\n'
    analog = scan['analog_pins']
    port, mask = analog['port'], number(analog['mask'])
    code += 'static inline void sn34_board_analog_pins(void){\n'
    for index, value in enumerate(analog['afio']):
        code += f'SN_ALWAYSON->P{port}_AFIO{index}={number(value)}u;\n'
    code += '}\nstatic inline void sn34_board_mux_phase(unsigned phase){\n'
    ports={}
    for bit,pin in enumerate(scan['mux_pins']):ports.setdefault(pin[0],[]).append((bit,pin[1]))
    for mux_port,mux_pins in ports.items():
        if len(mux_pins)==1:
            bit,pin=mux_pins[0]
            code += f'if(phase&(1u<<{bit})){{{gpio([mux_port,pin],True)}}}else{{{gpio([mux_port,pin],False)}}}\n'
        else:
            mux_mask=sum(1<<pin for bit,pin in mux_pins)
            expression='|'.join(f'(((phase>>{bit})&1u)<<{pin})' for bit,pin in mux_pins)
            code += f'uint32_t mux_p{mux_port}={expression};SN_GPIO{mux_port}->BSET=mux_p{mux_port};SN_GPIO{mux_port}->BCLR=mux_p{mux_port}^{mux_mask}u;\n'
    code += '}\nstatic inline void sn34_board_scan_pins_init(void){\n'
    for pin in scan['mux_pins'] + [scan['gate_pin']]:
        code += f'SN_GPIO{pin[0]}->DIR|=1u<<{pin[1]};\n'
    code += f'SN_GPIO{port}->PULLEN&=~{mask}u;SN_GPIO{port}->DIR&=~{mask}u;\n'
    code += '}\nstatic inline void sn34_board_sample_gate(void){' + gpio(scan['gate_pin'], False) + '}\n'
    code += 'static inline void sn34_board_scan_discharge(void){\n'
    for index in range(len(analog['afio'])):
        code += f'SN_ALWAYSON->P{port}_AFIO{index}=0;\n'
    code += f'SN_GPIO{port}->DIR|={mask}u;SN_GPIO{port}->BCLR={mask}u;'
    code += gpio(scan['gate_pin'], True) + 'sn34_board_analog_pins();}\n'
    code += f'static inline void sn34_board_scan_input(void){{SN_GPIO{port}->DIR&=~{mask}u;}}\n'
    channels = sorted({sample['channel'] for phase in scan['phases'] for sample in phase['samples']})
    code += 'static inline void sn34_board_read_adc(uint16_t *data,volatile const uint32_t *regs){\n'
    code += ''.join(f'data[{channel}]=regs[{channel}];' for channel in channels) + '}\n'
    code += 'static inline void sn34_board_rgb_pins(void){\n'
    if rgb is not None and rgb.get('enable') is not None:
        pin=rgb['enable']
        code += gpio(pin,True)+f'SN_GPIO{pin[0]}->DIR|=1u<<{pin[1]};\n'
    for field,signal in (('mosi','MO'),('sck','SCK')) if rgb is not None else ():
        port,pin=rgb[field]
        code += f'HAL_GPIO_SetAFIO(SN_GPIO{port},1u<<{pin},GPIO_P{port}{pin}_SPI_{signal}1);\n'
    code += '}\n'
    write_if_changed(build / 'hardware.generated.h', code)
