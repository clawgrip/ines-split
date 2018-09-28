import getopt
import os.path
import struct
import sys

HELP_TEXT = """\
Copies Trainer, PRG-ROM or CHR-ROM from an iNES ROM file (.nes) to a
new file.

Command line arguments: OUTPUT_FILES INPUT_FILE
    OUTPUT_FILES:
        Which parts to read from INPUT_FILE and names of files to write
        (one or more):
            -t OUTPUT_FILE, --trainer=OUTPUT_FILE
                Trainer (512 bytes)
            -p OUTPUT_FILE, --prg-rom=OUTPUT_FILE
                PRG-ROM
            -c OUTPUT_FILE, --chr-rom=OUTPUT_FILE
                CHR-ROM
        The files must not already exist (they will not be overwritten).
    INPUT_FILE:
        iNES ROM file to read.
        This argument is required.

Note: If the PRG-ROM or the CHR-ROM consists of a repeated chunk with
a length of a power of two, only one instance will be extracted. For
example, the Game Genie iNES file has 16 KiB of PRG-ROM but only 4 KiB
will be extracted because the rest is just the same data repeated.\
"""

# maximum size of buffer when reading files, in bytes
FILE_BUFFER_MAX_SIZE = 2 ** 20

# iNES file part sizes
HEADER_SIZE = 16
TRAINER_SIZE = 512  # if present
PRG_BANK_SIZE = 16 * 1024
CHR_BANK_SIZE = 8 * 1024

def to_ASCII(string):
    """Replace non-ASCII characters with backslash codes."""
    byteString = string.encode("ascii", errors="backslashreplace")
    return byteString.decode("ascii")

def validate_output_file(file):
    """Exit if output file is invalid."""
    if os.path.exists(file):
        exit("Error: file already exists: {:s}".format(to_ASCII(file)))
    dir = os.path.dirname(file)
    if dir != "" and not os.path.isdir(dir):
        exit("Error: directory does not exist: {:s}".format(to_ASCII(dir)))

def parse_arguments():
    try:
        (opts, args) = getopt.getopt(
            sys.argv[1:], "t:p:c:", ("trainer=", "prg-rom=", "chr-rom=")
        )
    except getopt.GetoptError:
        exit("Error: invalid argument")

    opts = dict(opts)

    # Trainer
    trainer = opts.get("--trainer", opts.get("-t"))
    if trainer is not None:
        validate_output_file(trainer)

    # PRG-ROM
    prg = opts.get("--prg-rom", opts.get("-p"))
    if prg is not None:
        validate_output_file(prg)

    # CHR-ROM
    chr = opts.get("--chr-rom", opts.get("-c"))
    if chr is not None:
        validate_output_file(chr)

    # at least one target file is required
    if trainer is None and prg is None and chr is None:
        exit("Error: nothing to do")

    # input file
    if len(args) != 1:
        exit("Error: invalid number of arguments")
    source = args[0]
    if not os.path.isfile(source):
        exit("Error: file not found: {:s}".format(to_ASCII(source)))

    return {
        "trainer": trainer,
        "prg": prg,
        "chr": chr,
        "source": source,
    }

def parse_iNES_header(header, file):
    """Parse an iNES header."""
    # extract fields
    fields = struct.unpack("4s4B8s", header)
    (id, prgBanks, chrBanks, flags6, flags7, reservedBytes) = fields
    # extract flags
    trainer = bool((flags6 >> 2) & 0b1)
    reservedFlags = flags7 & 0b1111
    # validate fields
    if id != b"NES\x1a":
        exit("Error: invalid identifier: {:s}".format(to_ASCII(file)))
    if reservedFlags != 0 or not all(byte == 0 for byte in reservedBytes):
        print("Warning: reserved header bits are nonzero: {:s}".format(
            to_ASCII(file)
        ))
    # return sizes of parts
    return {
        "trainer": trainer * TRAINER_SIZE,
        "prg": prgBanks * PRG_BANK_SIZE,
        "chr": chrBanks * CHR_BANK_SIZE,
    }

def get_iNES_info(handle):
    """Get and validate sizes of iNES file parts from header."""
    size = handle.seek(0, 2)
    if size < HEADER_SIZE:
        exit("Error: the file is smaller than the iNES header size.")
    # read and parse iNES header
    handle.seek(0)
    header = handle.read(HEADER_SIZE)
    info = parse_iNES_header(header, handle.name)
    # validate size
    correctSize = HEADER_SIZE + info["trainer"] + info["prg"] + info["chr"]
    if size != correctSize:
        msg = (
            "Error: the file is {:d} bytes; according to the header, it "
            "should be {:d} bytes (= header {:d} + trainer {:d} + PRG-ROM "
            "{:d} + CHR-ROM {:d} bytes)"
        ).format(
            size, correctSize, HEADER_SIZE, info["trainer"], info["prg"],
            info["chr"]
        )
        exit(msg)
    return info

def read_file(handle, pos, bytesLeft):
    """Yield a slice from a file in chunks."""
    while bytesLeft > 0:
        chunkSize = min(bytesLeft, FILE_BUFFER_MAX_SIZE)
        handle.seek(pos)  # must be set before each yield
        yield handle.read(chunkSize)
        pos += chunkSize
        bytesLeft -= chunkSize

def is_file_part_splittable(handle, start, length):
    """Can the PRG-ROM or CHR-ROM data be split in half? That is, are the
    halves identical, a power of two and large enough?"""
    # length must be 2**5 (two CHR tiles) to 2**21 (maximum PRG size)
    if length not in (2**exp for exp in range(5, 21+1)):
        return False
    halfLength = length // 2
    # compare halves chunk by chunk
    return all(
        chunk1 == chunk2 for (chunk1, chunk2) in zip(
            read_file(handle, start, halfLength),
            read_file(handle, start + halfLength, halfLength)
        )
    )

def copy_slice(source, bytesLeft, target):
    """Copy a slice from current position in source file to start of target
    file in chunks."""
    target.seek(0)
    while bytesLeft > 0:
        chunkSize = min(bytesLeft, FILE_BUFFER_MAX_SIZE)
        target.write(source.read(chunkSize))
        bytesLeft -= chunkSize

def copy_parts(source, settings):
    """Copy parts of input file to output files."""
    info = get_iNES_info(source)
    # Trainer
    if settings["trainer"] is not None:
        if info["trainer"] == 0:
            print("Warning: no Trainer: {:s}".format(to_ASCII(source.name)))
        else:
            source.seek(HEADER_SIZE)
            with open(settings["trainer"], "wb") as target:
                copy_slice(source, info["trainer"], target)
    # PRG-ROM
    if settings["prg"] is not None:
        if info["prg"] == 0:
            print("Warning: no PRG-ROM: {:s}".format(to_ASCII(source.name)))
        else:
            start = HEADER_SIZE + info["trainer"]
            length = info["prg"]
            # split in half as many times as possible
            while is_file_part_splittable(source, start, length):
                length //= 2
            # copy
            source.seek(start)
            with open(settings["prg"], "wb") as target:
                copy_slice(source, length, target)
    # CHR-ROM
    if settings["chr"] is not None:
        if info["chr"] == 0:
            print("Warning: no CHR-ROM: {:s}".format(to_ASCII(source.name)))
        else:
            start = HEADER_SIZE + info["trainer"] + info["prg"]
            length = info["chr"]
            # split in half as many times as possible
            while is_file_part_splittable(source, start, length):
                length //= 2
            # copy
            source.seek(start)
            with open(settings["chr"], "wb") as target:
                copy_slice(source, length, target)

def main():
    # parse arguments
    if len(sys.argv) == 1:
        print(HELP_TEXT)
        exit(0)
    settings = parse_arguments()
    # copy parts of input file to output files
    try:
        with open(settings["source"], "rb") as source:
            copy_parts(source, settings)
    except OSError:
        exit("File read/write error")

if __name__ == "__main__":
    main()
