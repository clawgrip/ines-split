# ines-extract
Extracts header, trainer, PRG-ROM or CHR-ROM from an iNES file ([Nintendo Entertainment System](http://en.wikipedia.org/wiki/Nintendo_Entertainment_System) (NES) ROM, extension `.nes`).

## Resources used
* [NESDev Wiki – iNES](http://wiki.nesdev.com/w/index.php/INES)

## Example

Extract the CHR-ROM data from `Super Mario Bros. (W) [!].nes` to `smb.chr`:
```
python ines-extract.py "Super Mario Bros. (W) [!].nes" c "smb.chr"
```
