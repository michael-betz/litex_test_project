from natsort import natsorted
from collections import defaultdict
import re


class XdcParser:
    def __init__(self, fName):
        '''
        fName is a Xilinx Master .xdc file from their website
        '''
        with open(fName) as f:
            lines = f.readlines()

        self.props = defaultdict(dict)
        for line in lines:
            line = line.strip()
            if line.startswith('#'):
                continue
            parts = line.split()
            if not parts[0] == 'set_property':
                continue
            if parts[3] == '[get_ports':
                self.props[parts[4].replace(']', '')][parts[1]] = parts[2]
            else:
                print('sorry, parser is too dumb for this:', parts)
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

    def getConnector(self, fmcName='FMC1_HPC', nameReplace=None):
        '''
        makes up litexNames from xilinx naming scheme

        example:
            p.getConnector(
                "XADC",
                nameReplace=(('N_R', '_N'), ('P_R', '_P'))
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
        fmcName_ = fmcName + '_'
        print('    ("{:}", {{'.format(fmcName))
        for k in self.filterKeys(fmcName_ + '.*'):
            pinName = k.replace(fmcName_, '')
            if nameReplace:
                for rep in nameReplace:
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
        print('Subsignal("{:}", Pins("{:}"){:}),'.format(
            liteName,
            pins,
            ios
        ))

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
            print('        ', end='')
            self.getSubSignal(*t)
        print('    ),')
