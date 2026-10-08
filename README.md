# FontInstaller

글꼴 파일, 폴더, zip을 읽어서 Windows에 자동으로 설치하는 파이썬 스크립트(Windows)

- 지원 형식: `.ttf` `.otf` `.ttc` `.otc`
- zip 안의 폴더, zip 안의 zip까지 설치 가능
- 원본 파일은 복사만 진행

## 환경 준비

1. [python.org](https://www.python.org/downloads/)에서 Python 설치 (설치 시 **Add python.exe to PATH** 체크)
2. 터미널(PowerShell)에서 라이브러리 설치

```
python -m pip install fonttools
```

### fonttools

- 글꼴의 실제 이름을 읽어 레지스트리에 정확하게 등록 가능
- 파일 명 기반 이름으로 등록하기 위해 필요
  
## 실행 방법

`FontInstaller.py`가 있는 폴더에서 실행합니다.

```py
# 압축 파일
python FontInstaller.py 글꼴.zip

# 폴더
python FontInstaller.py C:\fonts\MyFolder

# 위치 다중 설정 가능
python FontInstaller.py a.ttf b.otf 글꼴.zip C:\fonts
```

- 인자 없이 실행하면 파일 선택 창 로드(파일/zip만 선택 가능, 폴더는 명령줄로 입력)
- 경로에 공백이 있으면 `"따옴표"` 사용
- 파일이나 폴더를 PowerShell 창으로 드래그 시 경로 자동 입력

## 설치 방식

| 옵션 | 설치 대상 | 관리자 권한 |
| --- | --- | --- |
| (기본) | 현재 사용자 | 불필요 (Windows 10 1809 이상) |
| `--system` | 모든 사용자 | 필요 (UAC 창이 자동으로 뜸) |

```
python FontInstaller.py 글꼴.zip --system
```

## 참고

- 같은 글꼴은 건너뛰고 내용이 다를 경우에만 덮어쓰기
  - 사용 중인 글꼴은 덮어쓰기에 실패할 가능성 존재
- 글꼴 제거 기능 미개발
  - 제거는 Windows 설정 → 개인 설정 → 글꼴에서 개별 진행
- 글꼴 라이선스(상업적 사용 가능 여부 등)는 **사용자가 직접 확인 후 설치**
  - 해당 프로그램은 라이선스를 책임지지 않으므로 사용에 대한 책임은 **본인이 직접 감당하세요.**
