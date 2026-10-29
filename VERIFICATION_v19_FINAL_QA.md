# MGL v1.9 최종 QA 보완 기록

## 변경
- 프로젝트·이벤트·생활 선택 결과의 원시 JSON 출력 대신 필드별 읽기 쉬운 결과 목록으로 표시.
- 결과 값의 HTML 이스케이프와 긴 값 줄바꿈을 적용.
- 저장 목록 조회 실패 시 불러오기 UI에서 오류 안내를 표시.

## 검증
- `python -m unittest discover -s tests -p 'test*.py' -q`: 19/19 통과.
- `node --check web/app.js`: 통과.
- 로컬 HTTP API 직접 요청: 응답 확인.
- Chromium/Playwright 설치 확인. 그러나 브라우저가 `http://127.0.0.1` 접근을 `ERR_BLOCKED_BY_ADMINISTRATOR`로 차단하여 실제 브라우저 클릭/레이아웃 검증 불가.

## 범위와 제한
- 기존 게임 엔진 및 엔딩 조건 정의 파일 변경 없음.
- 모바일 반응형, 실제 클릭 시나리오, 48종 엔딩 화면별 수동 QA는 미검증.
- 이 결과물을 '브라우저 QA 완료'로 해석해서는 안 됨.
