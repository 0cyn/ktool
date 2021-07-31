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

dumping headers:
ktool dump --headers --out <directory> [filename]

```

Will document other features soon, more are on the way.

---

written in python for the sake of platform independence when operating on static binaries and libraries

#### Special thanks to

IDA for making it possible to write the code without actually understanding full internals  
JLevin and *OS Internals Vol 1 for actually understanding the internals and specifics + writing documentation  
arandomdev for guidance + code
