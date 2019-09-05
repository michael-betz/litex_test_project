from natsort import natsorted
from collections import defaultdict
import re


class XdcParser:
    def __init__(self, fName):
        ''' fName is a Xilinx Master .xdc file from their website '''
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
        ''' search schematic names with a regex '''
        pp = re.compile(regex)
        return [x for x in self.keys if pp.fullmatch(x)]

    def getGpios(self, liteName='user_led', xilRegex='GPIO_LED.*'):
        ''' print a single line per IO pin '''
        for i, k in enumerate(self.filterKeys(xilRegex)):
            print('    ("{:}", {:}, Pins("{:}"), IOStandard("{:}")),'.format(
                liteName,
                i,
                self.props[k]["PACKAGE_PIN"],
                self.props[k]["IOSTANDARD"]
            ))

    def getConnector(self, fmcName='FMC1_HPC', nameReplace=None):
        fmcName_ = fmcName + '_'
        print('    ("{:}", {{'.format(fmcName))
        for k in filter(lambda x: x.startswith(fmcName_), self.keys):
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
        liteName='rx_p'
        xilRegex: 'PCIE_RX[0-9]_P'
        maxPins: upper limit on the number of pins in the list
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
        print('    ("{:}", 0,'.format(name))
        for t in tuples:
            print('        ', end='')
            self.getSubSignal(*t)
        print('    ),')
