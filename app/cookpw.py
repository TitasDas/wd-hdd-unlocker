#!/usr/bin/env python3

from hashlib import sha256
import sys


def main(password):
    """Print the data block required to unlock the drive."""
    password_bytes = ('WDC.' + password).encode('utf-16')[2:]  # remove UTF-16 BOM

    for _ in range(1000):
        password_bytes = sha256(password_bytes).digest()

    header_hex = '45' + '0000000000' + '0020'
    header_bytes = bytes.fromhex(header_hex)
    payload = header_bytes + password_bytes

    out = getattr(sys.stdout, 'buffer', sys.stdout)
    out.write(payload)


def read_password_from_stdin():
    data = sys.stdin.read()
    if data is None:
        return ''
    return data.rstrip('\r\n')


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == '--stdin':
        main(read_password_from_stdin())
        sys.exit(0)

    if len(sys.argv) != 2:
        print(f'Usage: {sys.argv[0]} <password> | {sys.argv[0]} --stdin', file=sys.stderr)
        sys.exit(1)

    main(sys.argv[1])
