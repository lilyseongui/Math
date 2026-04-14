# MATH 수업 준비용 1페이지 요약

## 목표
영상 URL만 바꿔서 자막 앱을 다시 만들고, APK까지 배포한다.

## 준비물
- `.env`에 `OPENAI_API_KEY` 설정
- `videos.json`에 과목/영상 URL 입력
- 터미널에서 Python venv 사용 가능

## 실행 순서 (복붙용)

### 1) 자막 생성 + GPT 교정
```powershell
cd c:/Users/User/vibeCoding/YOUTUBE/MATH
& "c:/Users/User/vibeCoding/.venv/Scripts/python.exe" extract_and_check.py --proxy-mode none --spellcheck-engine gpt
```

### 2) 교정 적용 확인
```powershell
Get-ChildItem "generated/topics" -Recurse -Filter report.json | ForEach-Object {
  $r = Get-Content $_.FullName | ConvertFrom-Json
  Write-Host "$($r.topic): applied=$($r.spellcheck.applied), snippets=$($r.snippetCount)"
}
Get-Item "MathChatbotAndroid/app/src/main/assets/math_topics.json" | Select-Object Name, Length
```

### 3) APK 빌드
```powershell
cd c:/Users/User/vibeCoding/YOUTUBE/MATH/MathChatbotAndroid
./gradlew.bat assembleRelease
```

### 4) APK 위치 확인
```powershell
Get-ChildItem "app/build/outputs/apk/release" -Filter "*.apk"
```

## 수업 전 최종 체크
- [ ] `videos.json` 최신 반영
- [ ] `report.json`에서 `applied=True` 확인
- [ ] `math_topics.json` 크기 0 아님
- [ ] `app-release.apk` 생성 완료
- [ ] 휴대폰 설치 후 링크 클릭 시 시간 이동 확인

## 문제 발생 시 빠른 점검
- 교정 안 됨: `.env`의 `OPENAI_API_KEY` 확인
- 검색 결과 적음: `math_topics.json` 생성 여부 확인
- 링크 클릭 안 됨: 최신 APK 재설치

## 릴리즈 업로드
- 업로드 파일: `MathChatbotAndroid/app/build/outputs/apk/release/app-release.apk`
- GitHub Release 태그와 앱 `versionName` 일치 권장
