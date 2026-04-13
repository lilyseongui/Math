# YouTube 과목별 자막 파이프라인 + 오프라인 Android 챗봇

이 폴더는 두 가지를 같이 포함합니다.

1. 여러 유튜브 주소를 과목별 폴더로 나눠 자막과 맞춤법 검사 결과를 자동 생성하는 Python 파이프라인
2. 생성된 JSON 자산을 읽어 로컬 검색형 챗봇처럼 동작하는 Android 앱 스캐폴드

## Python 설치

```bash
pip install -r requirements.txt
```

## 프록시 설정

같은 폴더에 `.env` 파일을 만들고 Webshare 정보를 넣습니다.

```env
WEBSHARE_PROXY_USERNAME=여기에_아이디
WEBSHARE_PROXY_PASSWORD=여기에_비밀번호
```

## 입력 파일

[videos.json](videos.json) 에 과목명과 URL 목록을 넣습니다.

```json
{
	"subjects": [
		{
			"name": "벡터",
			"urls": [
				"https://www.youtube.com/watch?v=Fh9vBLIcuj4"
			]
		}
	]
}
```

## 파이프라인 실행

```bash
python extract_and_check.py
```

실행 결과:

- `generated/topics/<과목명>/<videoId>/transcript.json`
- `generated/topics/<과목명>/<videoId>/transcript.txt`
- `generated/topics/<과목명>/<videoId>/transcript_checked.txt`
- `generated/topics/<과목명>/<videoId>/report.json`
- `generated/app_assets/math_topics.json`
- `MathChatbotAndroid/app/src/main/assets/math_topics.json`

## 단일 영상만 실행

```bash
python extract_and_check.py --single --url "https://www.youtube.com/watch?v=VIDEO_ID"
```

## Android 앱 구조

Android 프로젝트는 [MathChatbotAndroid](MathChatbotAndroid) 아래에 있습니다.

- 앱은 `app/src/main/assets/math_topics.json` 을 읽습니다.
- 과목 칩을 선택한 뒤 질문하면 로컬 JSON에서 관련 자막 스니펫을 검색합니다.
- 서버 호출 없이 APK 설치형 오프라인 챗봇처럼 동작하도록 설계했습니다.

## APK 빌드

```bash
cd MathChatbotAndroid
gradlew.bat assembleDebug
```

## 구현 원칙

- 자막 요청은 반드시 `ytt_api.fetch(video_id)` 를 사용합니다.
- 프록시 설정은 `WebshareProxyConfig` 로 처리합니다.
- 한국어 자막인 경우에만 `py-hanspell` 맞춤법 검사를 적용합니다.
- Android 앱은 생성형 모델이 아니라 로컬 자막 검색 기반 챗봇 구조입니다.