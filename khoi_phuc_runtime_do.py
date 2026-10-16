"""Lấy thành phần CPU/Vulkan từ gói chính thức, không cài đè Ollama toàn máy."""
import hashlib
import json
from pathlib import Path
import struct
import zlib

import requests

URL = "https://github.com/ollama/ollama/releases/download/v0.40.4/ollama-windows-amd64.zip"
SIZE = 1469916992
DEST = Path(__file__).resolve().parent / ".runtime" / "ollama-0.40.4"
session = requests.Session()


def get_range(start, end):
    for attempt in range(3):
        try:
            r = session.get(URL, headers={"Range": f"bytes={start}-{end}"}, timeout=60)
            assert r.status_code == 206
            assert r.headers.get("Content-Range") == f"bytes {start}-{end}/{SIZE}"
            assert len(r.content) == end - start + 1
            return r.content
        except Exception:
            if attempt == 2:
                raise


def main():
    tail = get_range(SIZE - 65536, SIZE - 1)
    eocd = struct.unpack("<4s4H2LH", tail[tail.rfind(b"PK\x05\x06"):][:22])
    cd_size, cd_offset = eocd[5:7]
    cd = tail[cd_offset - (SIZE - 65536):][:cd_size]
    pos, entries = 0, []
    while cd[pos:pos+4] == b"PK\x01\x02":
        h = struct.unpack("<4s6H3L5H2L", cd[pos:pos+46])
        name = cd[pos+46:pos+46+h[10]].decode("utf-8")
        pos += 46 + h[10] + h[11] + h[12]
        if name.endswith("/") or "/cuda_" in name:
            continue
        assert ".." not in Path(name).parts and not Path(name).is_absolute()
        entries.append((name, h))
    records = []
    for name, h in entries:
        dest = DEST / name
        if dest.exists() and len(dest.read_bytes()) == h[9] and zlib.crc32(dest.read_bytes()) == h[7]:
            data = dest.read_bytes()
        else:
            offset, compressed = h[16], h[8]
            local = get_range(offset, offset+29)
            _, _, _, method, _, _, _, _, _, name_len, extra_len = struct.unpack("<4s5H3L2H", local)
            start = offset + 30 + name_len + extra_len
            raw = get_range(start, start+compressed-1)
            assert method in (0, 8)
            data = zlib.decompress(raw, -15) if method == 8 else raw
            assert len(data) == h[9] and zlib.crc32(data) == h[7]
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        records.append({"file":name,"sha256":hashlib.sha256(data).hexdigest(),"zip_crc32":h[7],"size":len(data)})
        print(name, flush=True)
    (DEST / "provenance.json").write_text(json.dumps({"url":URL,"version":"0.40.4","files":records},indent=2),encoding="utf-8")


if __name__ == "__main__":
    main()
