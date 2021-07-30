import os
import mmap
from kdump.headers import *
from kdump.ninja_generator import *
from kdump.macho.macho import MachO

class Framework:
    def __init__(self, name, root_location):
        # name = AACCore.framework
        self.rootloc = root_location
        self.name = name
        self.bin = name.split('.')[0]


    def build_headers(self, outdir):
        with open(self.rootloc + '/' + self.name + '/' + self.bin, "rb") as fd:
            with mmap.mmap(fd.fileno(), 0, access=mmap.ACCESS_READ) as file:
                macho = MachO(file)
                classlist = Classlist(macho)
                generator = HeaderGenerator(macho, classlist)

                for header_name, header in generator.headers.items():

                    os.makedirs(outdir + '/Headers/', exist_ok=True)
                    with open(outdir + '/Headers/' + header_name, 'w') as out:
                        out.write(str(header))


class SDKBuilder:
    def __init__(self, cachein, cacheout):
        if not cachein.endswith('/'):
            cachein += '/'
        if not cacheout.endswith('/'):
            cacheout += '/'
        self.cachein = cachein
        self.cacheout = cacheout
        self.frameworks = self._build_framework_list()
        with open('ninja.build', 'w') as file:
            ninja_writer = NinjaWriter(file)
            ninja_writer.rule('dump', 'python3 main.py --headers --out $out $in', 'Dumping Header for $in')
            for framework in self.frameworks:
                infile = cachein + '/System/Library/PrivateFrameworks/' + framework.name + '/' + framework.bin
                outdir = cacheout + '/System/Library/PrivateFrameworks/' + framework.name
                ninja_writer.build(outdir, 'dump', infile)


    def _build_framework_list(self):
        pfloc = self.cachein + '/System/Library/PrivateFrameworks'
        fw_name_list = os.listdir(pfloc)
        root_location = pfloc
        fw_list = []
        for name in fw_name_list:
            fw_list.append(Framework(name, root_location))
        return fw_list
