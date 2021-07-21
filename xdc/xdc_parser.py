from natsort import natsorted
from collections import defaultdict
import re


class XdcParser:
    def __init__(self, fName):
        '''
        fName is a Xilinx Master .xdc file from their website
        '''
        re_key = r'set_property\s(\w*)\s"?(\w*)"?\s\[get_ports\s"?([\w\[\]]*)"?\]'
        re_keys = r'set_property\s-dict\s\{([\w\s"]*)\}\s\[get_ports\s"?([\w\[\]]*)"?\]'

        with open(fName) as f:
            lines = f.readlines()

        # lines = (
        #     'set_property IOSTANDARD LVCMOS18 [get_ports USB_SMSC_NXT]',
        #     'set_property PACKAGE_PIN R5 [get_ports "DDR_RAS_n"]',
        #     'set_property PIO_DIRECTION "BIDIR" [get_ports "MIO[53]"]',
        #     'set_property -dict {PACKAGE_PIN A8 IOSTANDARD DIFF_HSTL_II_25} [get_ports FMC1_LA_24_N]'
        # )

        self.props = defaultdict(dict)
        for line in lines:
            line = line.strip()
            if line.startswith('#'):
                continue
            dat = re.findall(re_key, line)
            if len(dat) == 1:
                dat_key, dat_value, dat_group = dat[0]
                self.props[dat_group][dat_key] = dat_value
                continue

            dat = re.findall(re_keys, line)
            if len(dat) == 1:
                dat_items, dat_group = dat[0]
                dat_items = dat_items.split()
                for (k, v) in zip(dat_items[0::2], dat_items[1::2]):
                    self.props[dat_group][k] = v.replace('"', '')
                continue
            else:
                print('sorry, parser is too dumb for this:\n', line)

        self.sortKeys()

    def sortKeys(self):
        self.keys = natsorted(self.props.keys())

    def filterKeys(self, regex):
        '''
        search schematic names in .xdc file with a regex
        '''
        pp = re.compile(regex)
        return [x for x in self.keys if pp.fullmatch(x)]

    def getGpios(self, liteName='user_led', xilRegex=r'GPIO_LED.*'):
        '''
        one pin per line, can print multiple lines

        example:
            p.getGpios('user_led', r'GPIO_LED_[0-1]_LS')

        prints:
            ("user_led", 0, Pins("AM39"), IOStandard("LVCMOS18")),
            ("user_led", 1, Pins("AN39"), IOStandard("LVCMOS18")),
        '''
        for i, k in enumerate(self.filterKeys(xilRegex)):
            print('    ("{:}", {:}, Pins("{:}"), IOStandard("{:}")),'.format(
                liteName,
                i,
                self.props[k]["PACKAGE_PIN"],
                self.props[k]["IOSTANDARD"]
            ))

    def getConnector(
        self,
        namePrefix='FMC1_HPC_',
        pinReplace=None,
        noKeys=False,
        namePattern='.*',
        outName=None
    ):
        '''
        makes up litexNames from xilinx naming scheme

        noKeys: print a list instead of key/value pairs

        example:
            p.getConnector(
                "XADC",
                pinReplace=(('N_R', '_N'), ('P_R', '_P'))
            )

        prints:
            ("XADC", {
                "GPIO_0": "BA21",
                "GPIO_1": "BB21",
                "GPIO_2": "BB24",
                "GPIO_3": "BB23",
                "VAUX0_N": "AP38",
                "VAUX0_P": "AN38",
                "VAUX8_N": "AM42",
                "VAUX8_P": "AM41",
            }),
        '''
        if outName is None:
            outName = namePrefix.strip('_')
        ks = self.filterKeys(namePrefix + namePattern)
        print('    ("{:}", '.format(outName), end='')

        if noKeys:
            pins = [self.props[k]['PACKAGE_PIN'] for k in ks]
            print('"{:}"),'.format(' '.join(pins)))
        else:
            print('{')
            for k in ks:
                pinName = k.replace(namePrefix, '').strip('_')
                if pinReplace:
                    for rep in pinReplace:
                        pinName = pinName.replace(*rep)
                print('        "{:}": "{:}",'.format(
                    pinName,
                    self.props[k]['PACKAGE_PIN'])
                )
            print('    }),')

    def getSubSignal(self, liteName, xilRegex, maxPins=None):
        '''
        example:
            ('rx_p', r'PCIE_RX\d_P', 4),

        prints:
            Subsignal("rx_p", Pins("Y4 AA6 AB4 AC6")),
        '''
        pins = ''
        ks = self.filterKeys(xilRegex)
        if maxPins is not None:
            ks = ks[:maxPins]
            if len(ks) < maxPins:
                raise RuntimeError("Not enough matches!")
        for k in ks:
            pins += self.props[k]["PACKAGE_PIN"] + ' '
        pins = pins[:-1]
        try:
            # Let's hope all the IO standards are the same :p
            ios = self.props[k]["IOSTANDARD"]
            ios = ', IOStandard("{:}")'.format(ios)
        except Exception:
            ios = ''
            pass
        s = '("{:}", Pins("{:}"){:}),'.format(
            liteName,
            pins,
            ios
        )
        return s

    def getGroup(self, name, tuples):
        '''
        tuples should be:
            ('litexName', r'xilinx regex', 'max. number of pins')

        example:
            p.getGroup('i2c', (
                ('scl', r'IIC_SCL_MAIN_LS'),
                ('sda', r'IIC_SDA_MAIN_LS'),
            ))

        prints:
            ("i2c", 0,
                Subsignal("scl", Pins("AT35"), IOStandard("LVCMOS18")),
                Subsignal("sda", Pins("AU32"), IOStandard("LVCMOS18")),
            ),
        '''
        print('    ("{:}", 0,'.format(name))
        for t in tuples:
            print('        Subsignal' + self.getSubSignal(*t))
        print('    ),')
