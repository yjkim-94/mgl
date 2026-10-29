# MGL v1.9.3 Vercel 서버리스 리팩토링

## 구현
- 기존 Python 게임 엔진, 콘텐츠, 엔딩 정의를 유지한 채 `mgl_serverless.py`에 요청별 독립 세션 디스패처 추가
- `api/index.py`에 Vercel Python HTTP 함수 구현; `vercel.json`으로 정적 웹과 API 경로 연결
- 웹 UI는 외부 호스트에서 서버리스 API를 사용하고, 자동 저장/슬롯 저장은 브라우저 localStorage에 저장
- 로컬 실행(`python mgl_web.py`)은 기존 API를 그대로 사용

## 검증
- 기존 테스트 21개 + 신규 서버리스 테스트 4개 = 25개 통과
- JavaScript `node --check` 통과
- 서버리스 요청 상태 격리, 저장 복원, 새 게임, 힌트 설정, 유효하지 않은 행동 차단 검사

## 주의 및 미완료
- 실제 Vercel 배포/원격 URL에서의 실행은 아직 확인하지 못함
- 브라우저 localStorage 저장은 같은 브라우저/도메인에만 존재하며, 데이터 삭제/기기 변경 시 소실될 수 있음
- 클라우드 DB, 계정 로그인, 서버 측 영속 저장은 후속 단계
- 실제 브라우저 클릭 QA 및 48종 엔딩 화면 QA는 미완료
- 배포 환경에서 Python import 경로 및 서버리스 함수 제약은 실배포 후 확인 필요

## 실행
- 로컬: `python mgl_web.py --port 8765`
- Vercel: 이 디렉터리를 프로젝트 루트로 Git에 올린 뒤 Vercel에 연결해 Preview 배포
