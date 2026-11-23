# 서드파티 고지

확인일 2026-11-23. 버전별 소스·배포물에서 읽은 고지의 해시는 [고지 확인 출력](checks/license-evidence.txt)에 있습니다. 각 주소는 복사용 텍스트입니다.

| 구성요소 | 확인한 라이선스 및 시험에서의 사용 | 공식 원문 주소 |
|---|---|---|
| unhwp 0.24.0 및 수정 빌드 | MIT. 고정 커밋의 저작권과 허가·면책 고지를 아래에 원문으로 유지합니다. `Preserve` 표 렌더링 모드를 추가했습니다. 이 폴더에는 [수정 패치](bench/unhwp-0.24.0-preserve-tables.patch)가 있습니다. | `https://github.com/iyulab/unhwp/blob/965e9a2c14e12ff939e27e42094c932b08656c22/LICENSE` |
| kordoc 4.25.3 | MIT. npm 공식 버전의 `package/LICENSE`를 확인했습니다. 독립 실행 비교에 사용합니다. | `https://registry.npmjs.org/kordoc/-/kordoc-4.25.3.tgz` 안의 `package/LICENSE` · 공식 저장소 사본 `https://raw.githubusercontent.com/chrisryugj/kordoc/main/LICENSE` |
| hwp2md 0.5.0 | `Cargo.toml`의 `GPL-3.0-only` 선언과 GPL 3.0 원문을 확인했습니다. **번들 금지. 독립 프로세스로 실행한 비교 도구**입니다. | `https://github.com/hephaex/hwp2md/blob/v0.5.0/LICENSE` · 선언 `https://github.com/hephaex/hwp2md/blob/v0.5.0/Cargo.toml` |
| python-hwpx 7.0.0 | Apache-2.0. 공식 휠의 `LICENSE`를 확인했습니다. 고정 입력 생성과 원본 대조에 사용합니다. | `https://github.com/airmang/python-hwpx/blob/2e451dea68d3a89c62e7a12079c70f5dc9587b7a/LICENSE` · 배포 `https://pypi.org/project/python-hwpx/7.0.0/#files` |
| lxml 6.1.3 | BSD-3-Clause. 추가 라이브러리 고지는 `LICENSES.txt`에 있습니다. 테스트 입력 생성과 대조에 사용합니다. | `https://raw.githubusercontent.com/lxml/lxml/lxml-6.1.3/LICENSE.txt` · `https://raw.githubusercontent.com/lxml/lxml/lxml-6.1.3/LICENSES.txt` |
| markdown-it-py 4.0.0 | MIT. 포팅 원본의 별도 `LICENSE.markdown-it`도 확인했습니다. Markdown 파싱에 사용합니다. | `https://raw.githubusercontent.com/executablebooks/markdown-it-py/v4.0.0/LICENSE` · `https://github.com/executablebooks/markdown-it-py/blob/v4.0.0/LICENSE.markdown-it` |
| psutil 7.2.2 | BSD-3-Clause. 실험의 프로세스 자원 표본 수집에 사용합니다. | `https://raw.githubusercontent.com/giampaolo/psutil/release-7.2.2/LICENSE` |
| beautifulsoup4 4.14.3 | MIT. 공식 배포의 `LICENSE`를 확인했습니다. HTML 표를 대조하는 검수기에서 사용합니다. | `https://www.crummy.com/software/BeautifulSoup/bs4/download/4.14/beautifulsoup4-4.14.3.tar.gz` 안의 `LICENSE` |
| 간접 의존성 | [미확인] 잠금 파일에 참조된 구성요소의 배포 고지는 전수 심사 전입니다. | [시험 재현용 잠금 파일 설명](bench/README.md) |

## unhwp MIT 원문 고지

```text
MIT License

Copyright (c) 2025 iyulab

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## 형식 규격 및 공개 시험 입력

한컴 다운로드 센터의 HWP/OWPML 형식 페이지 중 「HWP 문서 파일 형식에 대한 사용권 및 저작권」에는 공개 문서를 참고한 개발 결과물에 참고 사실을 표시하는 조항이 있습니다. 2026-11-23에 해당 원문을 확인했습니다. 원문 URL은 [출처표](bench/SOURCES.md)에 있습니다.

[전문가 확인 필요] 이 폴더의 수정 패치는 기존 unhwp의 표 렌더링 옵션을 바꿉니다. 기반 엔진은 HWP 5.0 사양을 참조하지만, 재사용 엔진과 이 수정·배포 형태에 고지 조항이 적용되는지는 확인 전입니다. 공개 규격의 이용 조건과 코드 라이선스의 적용 범위를 확인한 뒤 이 프로젝트의 고지 문구를 정합니다. [수정 패치](bench/unhwp-0.24.0-preserve-tables.patch) · [기반 엔진 사양 참조 확인](checks/benchmark-evidence.txt)
