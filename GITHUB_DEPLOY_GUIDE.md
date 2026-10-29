# MGL GitHub → Vercel 배포

1. 이 ZIP의 압축을 해제합니다.
2. GitHub 저장소 https://github.com/yjkim-94/mgl 를 로컬에 clone합니다.
3. 압축 해제한 **내용물 전체**를 저장소 루트에 복사합니다(상위 폴더 없이).
4. `git add . && git commit -m "feat: deploy MGL v1.9.3" && git push origin main`
5. Vercel 연결된 mgl 프로젝트에서 빌드 상태를 확인합니다.

Python 게임 엔진, api/index.py, vercel.json, web/ 등이 모두 루트에 있어야 합니다.
로컬 저장 데이터 saves/ 및 __pycache__/ 는 배포에 포함하지 않았습니다.
