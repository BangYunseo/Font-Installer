"""
글꼴 설치 프로그램 (Windows)

입력: 글꼴 파일(.ttf .otf .ttc .otc), 폴더, .zip (섞어서 설치 가능)
  - 인자 없이 실행 시 파일 선택창 로드
  - .py 파일 위에 파일/폴더를 드래그앤드롭 가능

설치 방식
  - 기본: 현재 사용자 설치 (관리자 권한 불필요, Windows 10 1809 이상)
  - --system: 모든 사용자 설치 (관리자 권한 필요, 필요하면 자동으로 권한 상승 요청)

사용 예(README.md 확인 가능)
  python font_installer.py NotoSansKR.zip
  python font_installer.py C:\\fonts D:\\a.ttf --system

권장: pip install fonttools  (글꼴의 실제 이름을 읽어 레지스트리에 정확히 등록)
"""



import argparse
import ctypes
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import winreg
import zipfile
from pathlib import Path

FONT_EXTS = {".ttf", ".otf", ".ttc", ".otc"}
REG_PATH = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"
WM_FONTCHANGE = 0x001D
HWND_BROADCAST = 0xFFFF
SMTO_ABORTIFHUNG = 0x0002

SYSTEM_DIR = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Fonts"
USER_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Microsoft" / "Windows" / "Fonts"


# ---------------------------------------------------------------- 권한
def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin(paths: list[Path]) -> None:
    """같은 스크립트를 관리자 권한으로 다시 실행하고 현재 프로세스는 종료."""
    args = [str(Path(sys.argv[0]).resolve()), "--system", *[str(p) for p in paths]]
    params = subprocess.list2cmdline(args)
    ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
    if ret <= 32:
        print("[WARNING] 관리자 권한 요청이 거부되었거나 실패했습니다.")
        sys.exit(1)
    sys.exit(0)


# ---------------------------------------------------------------- 입력 수집
MAX_ZIP_DEPTH = 8  # zip 안의 zip을 몇 단계까지 풀지


def _member_name(info: zipfile.ZipInfo) -> str:
    """UTF-8 플래그가 없는 zip의 한글 파일명(cp949)이 깨지는 것을 보정."""
    if info.flag_bits & 0x800:
        return info.filename
    try:
        return info.filename.encode("cp437").decode("cp949")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return info.filename


def extract_fonts_from_zip(zip_path: Path, out_dir: Path, depth: int = 0) -> list[Path]:
    """zip 안의 글꼴을 out_dir에 풀어내어 재귀적으로 처리. 내부 경로는 쓰지 않고 파일명만 사용."""
    found: list[Path] = []
    if depth > MAX_ZIP_DEPTH:
        print(f"[SKIPPED] zip이 너무 깊게 중첩되어 건너뜁니다.: {zip_path.name}")
        return found
    try:
        with zipfile.ZipFile(zip_path) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                full_name = _member_name(info)
                name = Path(full_name).name
                if name.startswith("._") or "__MACOSX" in full_name:
                    continue
                suffix = Path(name).suffix.lower()
                if suffix not in FONT_EXTS and suffix != ".zip":
                    continue
                slot = Path(tempfile.mkdtemp(dir=out_dir))  # 같은 이름 충돌 방지
                target = slot / name
                with zf.open(info) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                if suffix == ".zip":
                    found += extract_fonts_from_zip(target, out_dir, depth + 1)
                else:
                    found.append(target)
    except zipfile.BadZipFile:
        print(f"[WARNING] 손상되었거나 올바르지 않은 zip: {zip_path.name}")
    return found


def collect_fonts(inputs: list[Path], tmp_dir: Path) -> list[Path]:
    fonts: list[Path] = []
    for p in inputs:
        if not p.exists():
            print(f"[NON-ROUTE] 경로를 찾을 수 없음: {p}")
        elif p.is_dir():
            for f in p.rglob("*"):
                if f.is_file():
                    if f.suffix.lower() in FONT_EXTS:
                        fonts.append(f)
                    elif f.suffix.lower() == ".zip":
                        fonts += extract_fonts_from_zip(f, tmp_dir)
        elif p.suffix.lower() == ".zip":
            fonts += extract_fonts_from_zip(p, tmp_dir)
        elif p.suffix.lower() in FONT_EXTS:
            fonts.append(p)
        else:
            print(f"[SKIPPED] 지원하지 않는 형식이라 건너뜀: {p.name}")
    # 중복 제거 (순서 유지)
    seen, unique = set(), []
    for f in fonts:
        key = str(f.resolve()).lower()
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique


# ---------------------------------------------------------------- 글꼴 이름
def registry_title(path: Path) -> str:
    """레지스트리 값 이름 (예: 'Noto Sans KR Regular (TrueType)')."""
    default_kind = "OpenType" if path.suffix.lower() in (".otf", ".otc") else "TrueType"
    try:
        from fontTools.ttLib import TTCollection, TTFont
    except ImportError:
        return f"{path.stem} ({default_kind})"

    try:
        if path.suffix.lower() in (".ttc", ".otc"):
            fonts = list(TTCollection(str(path), lazy=True).fonts)
        else:
            fonts = [TTFont(str(path), lazy=True)]
        names, kind = [], "TrueType"
        for f in fonts:
            n = f["name"].getDebugName(4) or f["name"].getDebugName(1)
            if n and n not in names:
                names.append(n)
            if f.sfntVersion == "OTTO":  # CFF 기반
                kind = "OpenType"
        if names:
            return f"{' & '.join(names)} ({kind})"
    except Exception as e:
        print(f"[RENAMED] 글꼴 이름 읽기 실패, 파일명으로 대체 ({path.name}): {e}")
    return f"{path.stem} ({default_kind})"


# ---------------------------------------------------------------- 설치
def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def install_font(src: Path, system: bool) -> str:
    """반환: 'installed' | 'updated' | 'same' | 'failed'"""
    dest_dir = SYSTEM_DIR if system else USER_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name

    status = "installed"
    try:
        if dest.exists():
            if sha256(dest) == sha256(src):
                status = "same"
            else:
                shutil.copy2(src, dest)  # 사용 중이면 PermissionError
                status = "updated"
        else:
            shutil.copy2(src, dest)
    except PermissionError:
        print(f"[FAILED] 복사 실패 (사용 중이거나 권한 없음): {src.name}")
        return "failed"
    except Exception as e:
        print(f"[FAILED] 복사 실패 ({src.name}): {e}")
        return "failed"

    try:
        root = winreg.HKEY_LOCAL_MACHINE if system else winreg.HKEY_CURRENT_USER
        # 시스템 설치는 파일명만, 사용자 설치는 전체 경로를 값으로 넣는 것이 Windows 방식
        value = src.name if system else str(dest)
        with winreg.CreateKeyEx(root, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, registry_title(dest), 0, winreg.REG_SZ, value)
    except Exception as e:
        print(f"[REGEDIT] 레지스트리 등록 실패 ({src.name}): {e}")
        return "failed"

    # 현재 세션에 즉시 반영
    ctypes.windll.gdi32.AddFontResourceW(str(dest))
    return status


def broadcast_font_change() -> None:
    ctypes.windll.user32.SendMessageTimeoutW(
        HWND_BROADCAST, WM_FONTCHANGE, 0, 0, SMTO_ABORTIFHUNG, 2000, None
    )


# ---------------------------------------------------------------- 진입점
def pick_with_dialog() -> list[Path]:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    files = filedialog.askopenfilenames(
        title="설치할 글꼴 파일 또는 zip 선택",
        filetypes=[
            ("글꼴/ZIP", "*.ttf *.otf *.ttc *.otc *.zip"),
            ("모든 파일", "*.*"),
        ],
    )
    root.destroy()
    return [Path(f) for f in files]


def main() -> None:
    if os.name != "nt":
        print("[WARNING] 이 프로그램은 Windows 전용입니다.")
        sys.exit(1)

    ap = argparse.ArgumentParser(description="글꼴/폴더/zip을 읽어 Windows에 설치")
    ap.add_argument("inputs", nargs="*", help="글꼴 파일, 폴더, zip")
    ap.add_argument("--system", action="store_true", help="모든 사용자용으로 설치 (관리자 권한)")
    args = ap.parse_args()

    interactive = not args.inputs
    inputs = [Path(p).resolve() for p in args.inputs] if args.inputs else pick_with_dialog()
    if not inputs:
        print("[NON-SELECTION] 선택된 파일이 없어 종료합니다.")
        return

    if args.system and not is_admin():
        print("[RESTART] 관리자 권한으로 다시 실행합니다...")
        relaunch_as_admin(inputs)

    with tempfile.TemporaryDirectory(prefix="fontinst_") as tmp:
        fonts = collect_fonts(inputs, Path(tmp))
        if not fonts:
            print("[WARNING] 설치할 글꼴 파일(.ttf/.otf/.ttc/.otc)을 찾지 못했습니다.")
        else:
            mode = "모든 사용자" if args.system else "현재 사용자"
            print(f"[INSTALL] {len(fonts)}개 글꼴 발견 → {mode} 대상으로 설치합니다.\n")
            counts = {"installed": 0, "updated": 0, "same": 0, "failed": 0}
            labels = {"installed": "설치", "updated": "갱신", "same": "이미 동일", "failed": "실패"}
            for f in fonts:
                st = install_font(f, args.system)
                counts[st] += 1
                print(f"  [{labels[st]}] {f.name}")
            broadcast_font_change()
            print("\n[COMPLETE] 완료: " + ", ".join(f"{labels[k]} {v}" for k, v in counts.items()))
            print("[RESTART] 일부 프로그램은 재시작해야 새 글꼴이 보입니다.")

    if interactive or args.system:
        input("\n엔터를 누르면 종료됩니다...")


if __name__ == "__main__":
    main()
