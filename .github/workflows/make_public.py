"""Sinh workflow cho KHO PUBLIC chạy thay kho private (Actions kho private hết phút miễn phí; kho public chạy miễn phí).

Dùng:  python tools/public_runner/make_public.py   ->  ghi các file vào tools/public_runner/out/
Rồi chép các file trong out/ vào  .github/workflows/  của kho public (xem README.md cùng thư mục).

Mỗi workflow vẫn đọc và ghi mã nguồn, ảnh, video, trạng thái ở kho PRIVATE (checkout bằng mã PRIVATE_REPO_TOKEN,
đẩy kết quả về kho private). Kho public chỉ là chỗ chạy. Tên file giữ nguyên để app gọi như cũ.
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent.parent / ".github" / "workflows"
OUT = HERE / "out"
PRIVATE = "phatnh91/fashion-affiliate-reels"
TOKEN = "${{ secrets.PRIVATE_REPO_TOKEN }}"
FILES = ["0-add-product", "1-prepare", "2-build", "3-post", "4-scheduled-post", "5-stats"]
HEADER = ("# TỰ SINH bằng tools/public_runner/make_public.py từ .github/workflows/{name} của kho private. Đừng sửa tay: sửa file gốc rồi sinh lại.\n"
          "# Chạy ở kho public (miễn phí), đọc/ghi dữ liệu ở kho private bằng secret PRIVATE_REPO_TOKEN.\n")


def sub1(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, f"không khớp đúng 1 chỗ: {old[:70]!r} ({text.count(old)})"
    return text.replace(old, new, 1)


def indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def steps(lines):
    starts = [i for i, l in enumerate(lines) if l.startswith("      - ")]
    return [(s, starts[k + 1] if k + 1 < len(starts) else len(lines)) for k, s in enumerate(starts)]


def drop_push_trigger(text: str) -> str:
    """Kho public không nhận sự kiện push của kho private: bỏ khối `push:` (app tự bấm dựng sau khi tải clip)."""
    lines, out, i = text.split("\n"), [], 0
    while i < len(lines):
        if lines[i].rstrip() == "  push:":
            i += 1
            while i < len(lines) and (lines[i].strip() == "" or indent(lines[i]) > 2):
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


def convert(name: str) -> str:
    text = (SRC / f"{name}.yml").read_text(encoding="utf-8").replace("\r\n", "\n")
    text = re.sub(r"^name: (.*)$", lambda m: f"name: {m.group(1)}", text, count=1, flags=re.M)
    if name == "2-build":
        text = drop_push_trigger(text)
        text = text.replace("# Tự chạy khi bạn push clip Veo vào clips/<batch>/, hoặc chạy tay.", "# Chạy khi app bấm Dựng video (kho public không tự chạy theo push clip).")
    lines = text.split("\n")
    out, prev = [], 0
    for s, e in steps(lines):
        out += lines[prev:s]
        blk = lines[s:e]
        joined = "\n".join(blk)
        if "uses: actions/checkout@v4" in joined:
            at = next(k for k, l in enumerate(blk) if "uses: actions/checkout@v4" in l)
            wi = next((k for k, l in enumerate(blk) if l.rstrip() == "        with:" or l.rstrip().endswith("with:  # chỉ lấy file cần để dựng video (bỏ app/, docs/, tests/ và ảnh mặc thử/garment/endpose: tải nhanh hơn)")), None)
            add = [f"          repository: {PRIVATE}", f"          token: {TOKEN}"]
            if wi is not None:
                blk = blk[:wi + 1] + add + blk[wi + 1:]
            else:
                blk = blk[:at + 1] + ["        with:"] + add + blk[at + 1:]
        if "GH_TOKEN: ${{ github.token }}" in joined:
            nb = []
            for l in blk:
                if "GH_TOKEN: ${{ github.token }}" in l:
                    pad = l[:indent(l)]
                    if "post.py" in joined:  # dấu chống đăng trùng ghi thẳng vào kho private
                        nb += [f"{pad}GH_TOKEN: {TOKEN}", f"{pad}TARGET_REPO: {PRIVATE}"]
                    else:  # scheduler gọi `gh workflow run 3-post.yml` ngay trong kho public
                        nb += [l, f"{pad}GH_REPO: ${{{{ github.repository }}}}"]
                else:
                    nb.append(l)
            blk = nb
        if "python src/prepare.py" in joined or "python src/character.py" in joined:
            blk = [l for l in blk]
            pad = next((l[:indent(l)] for l in blk if "XOAI_WORKFLOW_TOKEN" in l), None)
            if pad is not None:
                at = next(k for k, l in enumerate(blk) if "XOAI_WORKFLOW_TOKEN" in l)
                blk = blk[:at + 1] + [f"{pad}TARGET_REPO: {PRIVATE}"] + blk[at + 1:]
        out += blk
        prev = e
    out += lines[prev:]
    return HEADER.format(name=f"{name}.yml") + "\n".join(out)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for n in FILES:
        (OUT / f"{n}.yml").write_text(convert(n), encoding="utf-8", newline="\n")
    print("Đã sinh:", ", ".join(FILES), "->", OUT)


if __name__ == "__main__":
    main()
