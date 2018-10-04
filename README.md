# ines-split
Splits an iNES ROM file (extension `.nes`) to PRG-ROM, CHR-ROM and Trainer data files.

Developed with Python 3 under 64-bit Windows.

This program was formerly known as *ines-extract*.

Hint: my [`ines-combine`](http://github.com/qalle2/ines-combine/) does the reverse thing (combines the data files back to an iNES ROM file).

## Resources used
* [NESDev Wiki – iNES](http://wiki.nesdev.com/w/index.php/INES)

## Example

Extract the PRG-ROM data to `smb.prg` and the CHR-ROM data to `smb.chr` from `smb.nes`:
```
python ines_split.py -p smb.prg -c smb.chr smb.nes
```
