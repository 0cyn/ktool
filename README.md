# ktool
Static Mach-O binary metadata analysis tool / information dumper
---

### Installation

```shell
pip3 install k2l
```

### Usage

```shell
usage: ktool [command] <flags> [filename]

ktool dump:
ktool dump --headers --out <directory> [filename] - Dump set of headers for a bin/framework
ktool dump --tbd [filename] - Dump .tbd for a framework

ktool file:
ktool file [filename] - Prints (very) basic info about a file (e.g. "Thin MachO Binary")

ktool info:
usage: ktool info [-h] [--slice SLICE_INDEX] [--vm] [--cmds] [--binding] filename
ktool info [--slice n] [filename] - Print generic info about a MachO File
ktool info [--slice n] --vm [filename] - Print VM -> Slice -> File address mapping for a slice of a MachO File
ktool info [--slice n] --cmds [filename] - Print list of load commands for a file 
ktool info [--slice n] --binding [filename] - Print binding actions for a file

```

Will document other features soon, more are on the way.

---

written in python for the sake of platform independence when operating on static binaries and libraries

#### Special thanks to

IDA for making it possible to write the code without actually understanding full internals  
JLevin and *OS Internals Vol 1 for actually understanding the internals and specifics + writing documentation  
arandomdev for guidance + code
