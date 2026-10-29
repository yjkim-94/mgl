# MGL v1.9 QA 보완 보고서

## 기준
MGL_v1.9_QA_patch_verified.zip

## 변경
- 모달에 dialog 접근성 속성 및 제목 연결 추가
- Escape 닫기, 닫은 뒤 이전 포커스 복원
- 좁은 화면 상단 메뉴·활동 카드·NPC 카드 CSS 보완
- QA 정적 테스트 2개 추가
- 브라우저 검증 재실행 스크립트 추가 (tests/test_v19_browser_qa.py)

## 검증
- `python -m unittest discover -s tests -p 'test*.py' -q`: 21/21 통과
- `node --check web/app.js`: 통과
- Chromium Playwright 직접 접속: ERR_BLOCKED_BY_ADMINISTRATOR
- Playwright 요청 중계 접속: ERR_BLOCKED_BY_ADMINISTRATOR

## 한계
브라우저 시각적 렌더링, 실제 모바일 클릭, 48개 엔딩 화면 각각의 UI는 검증되지 않았습니다. 브라우저 테스트 스크립트는 환경 차단으로 통과하지 않았으며 21개 통과 수에 포함하지 않았습니다. 게임 엔진 및 엔딩 정의는 수정하지 않았습니다.

## 다음 단계
브라우저 접속 가능한 개발 환경에서 `python tests/test_v19_browser_qa.py` 실행 후 레이아웃·인터랙션·엔딩 UI 수동 검토. v2.0 착수 전 세션 분리 확인.
