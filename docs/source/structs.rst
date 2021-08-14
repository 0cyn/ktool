structs
---------------------

ktool uses non-standard conventions for struct loading. They've been chosen for clarity and reduced overhead.


MachO Structs
*********************

fat_header
=====================

Represents the first 8 bytes of a MachO File

.. list-table:: 
    :widths: 5 1 10

    * - Field
      - Size 
      - Description 
    * - magic 
      - 4 
      - File magic. For a fat file, will always be 0xCAFEBABE
    * - nfat_archs
      - 4
      - Number of fat_archs in the file


fat_arch
=====================

At the beginning of a MachO File, after the header, several fat_arch structs are located, containing information about the slices within the file.

.. list-table:: 
   :widths: 5 1 10

   * - Field
     - Size
     - Description
   * - cputype
     - 4
     - CPUType Item
   * - cpusubtype
     - 4
     - CPU Subtype Item
   * - offset 
     - 4
     - Offset in file of the slice 
   * - size 
     - 4 
     - Size in bytes of the slice 
   * - align 
     - 4 
     - Address alignment of struct, as a power of 2 (2^align).


Dyld Structs
*********************

dyld_header
=====================

First 32 bytes of a Slice/Thin MachO File

.. list-table::
   :widths: 5 1 10

   * - Field
     - Size
     - Description
   * - magic
     - 4
     - File magic (0xFEEDFACE/0xFEEDFACF)
   * - cputype
     - 4
     - CPU Type
   * - cpusubtype
     - 4
     - CPU Subtype
   * - filetype
     - 4
     - ?
   * - loadcnt
     - 4
     - Number of load commands
   * - loadsize
     - 4
     - Size of load commands
   * - flags
     - 4
     - ?
   * - void
     - 4
     - ?


Load commands
*********************

dylib_command
=====================

Command that represents a dylib

.. list-table::
   :widths: 5 1 10

   * - Field
     - Size
     - Description
   * - cmd
     - 4
     - Load command
   * - cmdsize
     - 4
     - Size of load command (including string in dylib struct)
   * - dylib
     - 4
     - CPU Subtype
   * - filetype
     - 4
     - ?

dylib
^^^^^^^^^^^^^^^^^^^^^

Struct representing a dylib

.. list-table::
   :widths: 5 1 10

   * - Field
     - Size
     - Description
   * - name
     - 4
     - lc_str Offset of the load command string from the beginning of the dylib_command struct
   * - timestamp
     - 4
     - ?
   * - current_version
     - 4
     - ?
   * - compatibility_version
     - 4
     - ?