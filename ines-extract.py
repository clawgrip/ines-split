import os.path
import struct
import sys

HELP_TEXT = """\
Copies header, trainer, PRG-ROM or CHR-ROM from an iNES ROM file (.nes) to a
new file.

Command line arguments: INPUT_FILE PART [OUTPUT_FILE]
    INPUT_FILE
        File to read.
        This argument is required.
    PART
        Which part to extract from the input file:
            H   header
            T   trainer
            P   PRG-ROM
            C   CHR-ROM
        This argument is required.
        This argument is case insensitive.
    OUTPUT_FILE
        File to write.
        This argument is optional.
        The default value is INPUT_FILE but in current directory and the
        extension replaced as follows:
            header:  .hdr
            trainer: .trn
            PRG-ROM: .prg
            CHR-ROM: .chr
        The file must not already exist (it will not be overwritten).

Note: If the PRG-ROM or the CHR-ROM consists of a repeated chunk with a length
of a power of two, only one instance will be extracted. For example, the Game
Genie iNES file has 16 KiB of PRG-ROM but only 4 KiB will be extracted because
the rest is just the same data repeated.

Exit status (Windows %ERRORLEVEL%):
    4: syntax error or error in arguments
    3: error reading/writing files
    2: the input file is an invalid iNES file
    1: the requested part was not found in the input file
    0: success\
"""

# maximum size of buffer when reading files, in bytes
FILE_BUFFER_MAX_SIZE = 2 ** 20

OUTPUT_FILE_EXTENSIONS = {
    "H": ".hdr",
    "T": ".trn",
    "P": ".prg",
    "C": ".chr",
}

# exit status
SYNTAX_ERROR = 4
READ_WRITE_ERROR = 3
INES_ERROR = 2
PART_ERROR = 1

# iNES file part sizes
HEADER_SIZE = 16
TRAINER_SIZE = 512  # if present
PRG_BANK_SIZE = 16 * 1024
CHR_BANK_SIZE = 8 * 1024

def to_ASCII(string):
    """Replace non-ASCII characters with backslash codes."""
    byteString = string.encode("ascii", errors="backslashreplace")
    return byteString.decode("ascii")

def error(status, text, file = None):
    """Print error message to stderr and exit."""
    if file is None:
        file = ""
    else:
        file = "{:s}: ".format(to_ASCII(os.path.basename(file)))
    print("{:s}error: {:s}".format(file, text), file=sys.stderr)
    exit(status)

def warning(text, file = None):
    """Print warning message to stderr and continue."""
    if file is None:
        file = ""
    else:
        file = "{:s}: ".format(to_ASCII(os.path.basename(file)))
    print("{:s}warning: {:s}".format(file, text), file=sys.stderr)

def parse_iNES_header(header, filename):
    """Parse an iNES header."""

    # extract fields
    fields = struct.unpack("4s4B8s", header)
    (id, prgBanks, chrBanks, flags6, flags7, reservedBytes) = fields

    # extract flags
    trainer = bool((flags6 >> 2) & 0b1)
    reservedFlags = flags7 & 0b1111

    # validate fields
    if id != b"NES\x1a":
        error(INES_ERROR, "invalid identifier in header", filename)
    if prgBanks == 0:
        warning("no PRG-ROM", filename)
    if reservedFlags != 0x00:
        warning("reserved bits in header byte 7 are nonzero", filename)
    if not all(byte == 0x00 for byte in reservedBytes):
        msg = "reserved bytes in header (8-15) are nonzero: {:s}".format(
            " ".join(format(byte, "02x") for byte in reservedBytes)
        )
        warning(msg, filename)

    return {
        "prg": prgBanks * PRG_BANK_SIZE,
        "chr": chrBanks * CHR_BANK_SIZE,
        "trainer": trainer * TRAINER_SIZE,
    }

def get_iNES_info(handle):
    """Get and validate sizes of iNES file parts from header."""
    size = handle.seek(0, 2)
    if size < HEADER_SIZE:
        error(
            INES_ERROR, "the file is smaller than the iNES header size.",
            handle.name
        )
    # read and parse iNES header
    handle.seek(0)
    header = handle.read(HEADER_SIZE)
    info = parse_iNES_header(header, handle.name)
    # validate size
    correctSize = HEADER_SIZE + info["trainer"] + info["prg"] + info["chr"]
    if size != correctSize:
        msg = (
            "the file is {:d} bytes; according to the header, it should be "
            "{:d} bytes (= header {:d} + trainer {:d} + PRG-ROM {:d} + "
            "CHR-ROM {:d} bytes)"
        ).format(
            size, correctSize, HEADER_SIZE, info["trainer"], info["prg"],
            info["chr"]
        )
        error(INES_ERROR, msg, handle.name)
    return info

def read_file_in_chunks(handle, start, bytesLeft):
    """Yield a slice from a file in chunks."""
    handle.seek(start)

    while bytesLeft > 0:
        chunkSize = min(bytesLeft, FILE_BUFFER_MAX_SIZE)
        yield handle.read(chunkSize)
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
            read_file_in_chunks(handle, start, halfLength),
            read_file_in_chunks(handle, start + halfLength, halfLength)
        )
    )

def copy_part(source, part, target):
    """Copy part of source file to target file."""
    info = get_iNES_info(source)

    if part == "H":
        start = 0
        length = HEADER_SIZE
    elif part == "T":
        start = HEADER_SIZE
        length = info["trainer"]
    elif part == "P":
        start = HEADER_SIZE + info["trainer"]
        length = info["prg"]
    elif part == "C":
        start = HEADER_SIZE + info["trainer"] + info["prg"]
        length = info["chr"]
    else:
        exit("Invalid part argument.")  # should never happen

    if length == 0:
        error(PART_ERROR, "requested part not found", source.name)

    # split PRG or CHR data in half as many times as possible
    if part in ("P", "C"):
        while is_file_part_splittable(source, start, length):
            length //= 2

    target.seek(0)
    for chunk in read_file_in_chunks(source, start, length):
        target.write(chunk)

def main():
    # parse arguments
    if len(sys.argv) == 1:
        print(HELP_TEXT)
        exit(0)
    elif 3 <= len(sys.argv) <= 4:
        (source, part) = sys.argv[1:3]
        part = part.upper()
        target = sys.argv[3].upper() if len(sys.argv) == 4 else None
    else:
        error(SYNTAX_ERROR, "syntax error; run without arguments to see help")
    # validate arguments
    if part not in ("P", "C", "H", "T"):
        error(SYNTAX_ERROR, "invalid part argument")
    if os.path.isdir(source):
        error(READ_WRITE_ERROR, "is a directory", source)
    if not os.path.isfile(source):
        error(READ_WRITE_ERROR, "does not exist", source)
    # create and validate output file name
    if target is None:
        base = os.path.basename(source)
        target = os.path.splitext(base)[0] + OUTPUT_FILE_EXTENSIONS[part]
    if os.path.exists(target):
        error(READ_WRITE_ERROR, "the output file already exists", source)
    targetDir = os.path.dirname(target)
    if targetDir != "" and not os.path.isdir(targetDir):
        error(READ_WRITE_ERROR, "the output directory does not exist", source)
    # copy part of input file to output file
    try:
        with open(source, "rb") as sourceHnd, open(target, "wb") as targetHnd:
            copy_part(sourceHnd, part, targetHnd)
    except OSError:
        error(READ_WRITE_ERROR, "read/write error", file)

if __name__ == "__main__":
    main()
