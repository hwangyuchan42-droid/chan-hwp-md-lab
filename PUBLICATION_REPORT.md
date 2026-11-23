# 공개판 편집 기록 · 2026-11-23

## 편집 기록

- [확정] 합성 기준선 보고서에 형식별 비교와 판정 한계, 타이머 범위·실행 순서·캐시·정답·중단 후 재실행 조건을 복원했다. 장치 모델과 OS 빌드 번호는 비공개 상태로 두었다. [합성 측정 결과](bench/RESULTS.md)
- [확정] 감사 6절에 같은 실행 파일의 세션 간 변동과 해석 범위를 기록했고, BLOCKERS에 사람이 대조하지 않은 범위를 적었다. 2절의 108번째 표 차이 표 다음, 본문 분류 앞에 있던 앞뒤 문단 인용 두 줄은 공개판에서 삭제된 상태다. [감사 보고서](bench/AUDIT_2026-11-23.md)
- [확정] README에 도구별 표·본문 일치 차이를 추가했다. 라이선스 문구를 중립화했고, 한컴 안내의 표시 조항 출처와 적용 여부를 점검할 범위를 명시했다. [README](README.md) · [서드파티 고지](THIRD_PARTY_LICENSES.md)
- [검증됨] 두 합성 JSONL 원장은 첫 번째 inventory 레코드의 `logical_cpus`와 `ram_bytes`만 삭제했다. 키 삭제를 반영한 두 JSON의 키·값·유형·배열 순서를 비교했고, 첫 줄 이후에는 원본과 공개본의 줄 내용도 바이트 단위로 대조했다. 나머지 데이터 변경은 각각 0건이다. [명령과 출력](checks/jsonl-audit.txt) · [검증 스크립트](checks/verify_jsonl.py) · [증빙 해시](checks/SHA256SUMS.txt)

| 원장 | 편집 전 SHA-256 | 편집 후 SHA-256 | 삭제 키 외 JSON 변경 |
|---|---|---|---:|
| `2026-11-22.jsonl` | `b1767dbedfec5e25cf146f448ed1d243b4caf8c79369d96a463ff282830af94e` | `e70c86b33625bc4d7ed4d352ef9dcb2c837901ec7ff1778c3941973a772762be` | 0 |
| `2026-11-23-mixed.jsonl` | `1fc448f2fa023666f5a47781546c5d17387e14655c878905c890eb1688ea706f` | `8cb90e8b70e26cf3b65e3b37128914bdc5bdfd54b15ddd8b839a3f8dd3dfef7d` | 0 |

공개 폴더에서 실행한다. 인수는 편집 전 원장 두 파일이 있는 디렉터리다.

```powershell
python -X utf8 .\checks\verify_jsonl.py '<편집 전 원장 디렉터리>'
```

## 개인정보 점검 요약

[검증됨] 공개판 파일명·내용과 합성 입력 내부 스트림에서 전자우편 주소, 사용자 경로, 알려진 개인정보 표기, 동기화 경로, 장치 식별 정보, 삭제한 인용문의 일치 건수는 모두 0이었다. 검색 결과는 알려진 이름과 패턴의 자동 검사 범위다. [검색 출력](checks/privacy.txt) · [상대 링크 검사](checks/links.txt) · [fixture 해시 검사](checks/fixtures.txt) · [회귀 테스트](checks/unittest.txt) · [증빙 해시](checks/SHA256SUMS.txt)
