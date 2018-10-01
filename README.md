# ines-extract
Extracts the Trainer, the PRG-ROM or the CHR-ROM from an iNES ROM file (extension `.nes`).

Hint: my [`ines-combine.py`](http://github.com/qalle2/ines-combine/) does the reverse thing (combines the data files back to an iNES ROM file).

Developed with Python 3 under 64-bit Windows.

## Resources used
* [NESDev Wiki – iNES](http://wiki.nesdev.com/w/index.php/INES)

## Example

Extract the PRG-ROM data to `smb.prg` and the CHR-ROM data to `smb.chr` from `smb.nes`:
```
python ines-extract.py -p smb.prg -c smb.chr smb.nes
```
