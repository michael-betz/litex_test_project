from sys import argv, exit
from litex.soc.integration.builder import Builder
from os import system

def main(soc, doc=''):
    if len(argv) < 2:
        print(doc)
        exit(-1)
    tName = argv[0].replace(".py", "")
    vns = None
    if "build" in argv:
        builder = Builder(
            soc, output_dir="build", csr_csv="build/csr.csv",
            compile_gateware=False, compile_software=False
        )
        vns = builder.build(
            build_name=tName, regular_comb=False, blocking_assign=True
        )
        # Ugly workaround as I couldn't get vpath to work :(
        system('cp ./build/gateware/mem*.init .')
    if "synth" in argv:
        builder = Builder(
            soc, output_dir="build", csr_csv="build/csr.csv",
            compile_gateware=True, compile_software=True
        )
        vns = builder.build(build_name=tName)
    if "config" in argv:
        prog = soc.platform.create_programmer()
        prog.load_bitstream("build/gateware/{:}.bit".format(tName))
    print(vns)
    try:
        soc.do_exit(vns)
    except:
        pass
