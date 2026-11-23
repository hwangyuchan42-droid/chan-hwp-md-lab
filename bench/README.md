# 로컬 실행과 재현

Windows x64에서 계측했습니다. 설치·빌드 예시는 프로젝트 루트에서 PowerShell로 실행합니다. 비교 도구와 공개 실문서 원본은 각 배포처에서 별도로 확보합니다. [배포처와 공개 자료](SOURCES.md)

## 1. 비교 도구

- Python 3.11과 Node.js 24 계열을 준비합니다. 검수 환경에 `markdown-it-py==4.0.0`, `psutil==7.2.2`, `beautifulsoup4==4.14.3`, `python-hwpx==7.0.0`, `lxml==6.1.3`을 설치합니다.
- 자신이 지정한 작업 경로를 `$toolRoot`로 두고, unhwp 0.24.0 Windows x64의 `unhwp.exe`를 그 아래 `unhwp/unhwp.exe`, 공식 C ABI DLL을 `ffi/unhwp.dll`에 놓습니다.
- [npm 잠금](locks/package-lock.json)과 [패키지 선언](locks/package.json)을 작업 경로에 복사하고 그 위치에서 `npm ci --omit=optional --ignore-scripts --no-audit --no-fund`를 실행합니다.
- hwp2md v0.5.0 소스는 `hwp2md-0.5.0-source`에 따로 준비합니다. [측정에 쓴 Cargo.lock](locks/Cargo.lock)을 해당 소스에 복사합니다. 소스 폴더에서 `cargo build --release --locked --target-dir ../hwp2md-target`로 빌드합니다. 이 실행 파일은 독립 비교 도구입니다.

## 2. 합성 기준선

[고정 합성 입력](fixtures/manifest.json)의 폴더를 작업 경로 아래 `fixtures`로 복사합니다. 아래 예시의 결과는 매번 새 파일을 지정합니다.

```powershell
python -X utf8 .\bench\baseline.py $toolRoot .\bench\repeat.jsonl
python -X utf8 .\bench\summarize.py .\bench\repeat.jsonl
```

공개 원장에 포함된 CPU 수·메모리 총량 항목은 공개용 복사 과정에서 제거했습니다. 새로 실행하면 실험기가 수집하는 원래 필드가 출력됩니다. 측정 횟수와 점수는 [합성 결과](RESULTS.md)에 있습니다.

## 3. 실문서 비교 및 수정 DLL

[출처표](SOURCES.md)의 보도자료 HWPX를 `release.hwpx`로, 붙임 HWP를 `appendix.hwp`로 저장하고 로컬 입력 폴더를 `$publicInputs`로 지정합니다. 해시는 [실문서 공개 원장](results/2026-11-23-final-body.jsonl)에서 확인할 수 있고, 검수기는 입력 해시를 확인한 후 변환합니다.

unhwp 커밋 `965e9a2c14e12ff939e27e42094c932b08656c22`을 별도 체크아웃에 준비한 뒤, [패치](unhwp-0.24.0-preserve-tables.patch)를 적용해 빌드합니다. 최초 측정은 Rust 1.95.0 GNU 및 MinGW-w64 환경을 사용했습니다.

```powershell
$patch = (Resolve-Path '.\bench\unhwp-0.24.0-preserve-tables.patch').Path
$upstream = Join-Path $toolRoot 'unhwp-0.24.0-source'
$build = Join-Path $toolRoot 'unhwp-table-target'
git -C $upstream apply --check $patch
git -C $upstream apply $patch
cargo build --manifest-path "$upstream\Cargo.toml" --release --locked --target-dir $build -p unhwp-cli -p unhwp --features unhwp/ffi
$patchedDll = Join-Path $build 'release\unhwp.dll'
python -X utf8 .\bench\public_benchmark.py $toolRoot $publicInputs .\bench\public-repeat.jsonl --preserve-library $patchedDll
```

HWP의 기본 정답은 최종본 `BodyText`입니다. 구 기준을 재현하려면 마지막 명령에 `--review-view`를 추가합니다. [실문서 감사](AUDIT_2026-11-23.md)

