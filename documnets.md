# MATH 프로젝트 소스코드 문서

이 문서는 YOUTUBE/MATH 프로젝트의 실제 소스코드를 기준으로 작성한 개발 문서입니다.

관련 문서:
- 교사용 설명 문서: documents_teacher.md
- 개발자 요약 문서: documents_developer.md

## 1. 시스템 개요

이 프로젝트는 두 계층으로 구성됩니다.

1. Python 데이터 생성 파이프라인
- videos.json 에 정의된 과목별 YouTube URL을 읽습니다.
- youtube-transcript-api 로 자막을 가져옵니다.
- 필요하면 GPT 또는 hanspell 로 한국어 맞춤법을 교정합니다.
- Android 앱이 바로 읽을 수 있는 math_topics.json 을 생성합니다.

2. Android 오프라인 검색형 챗봇 앱
- app/src/main/assets/math_topics.json 을 로드합니다.
- 사용자가 선택한 과목과 질문을 기준으로 자막 스니펫을 검색합니다.
- 점수 상위 3개 결과를 대화형 UI로 보여주고, 클릭 가능한 YouTube 타임스탬프 링크를 제공합니다.

핵심 설계 원칙은 서버 호출 없이 로컬 JSON 자산만으로 앱이 동작하는 오프라인 우선 구조입니다.

## 2. 디렉터리 구조

주요 파일과 폴더는 다음과 같습니다.

- extract_and_check.py
  - 데이터 생성 파이프라인의 단일 엔트리 포인트입니다.
- videos.json
  - 과목명과 YouTube URL 목록을 정의하는 입력 파일입니다.
- .env
  - 프록시 및 OpenAI 관련 비밀 설정을 저장합니다.
- generated/
  - 자막, 교정 결과, 리포트, 앱용 JSON 자산이 생성되는 폴더입니다.
- MathChatbotAndroid/
  - Android 앱 프로젝트 루트입니다.
- MathChatbotAndroid/app/src/main/assets/math_topics.json
  - 앱이 실행 시 읽는 최종 자산 파일입니다.

generated 폴더는 다시 아래처럼 나뉩니다.

- generated/topics/
  - 과목 및 영상 단위 중간 산출물 저장 위치
- generated/app_assets/
  - 앱에서 소비하는 최종 결합 JSON 저장 위치
- generated/single/
  - --single 옵션 실행 시 단일 영상 출력 위치

## 3. Python 파이프라인 상세

### 3.1 외부 의존성

requirements.txt 기준 주요 의존성은 아래와 같습니다.

- youtube-transcript-api
  - 자막 조회에 사용됩니다.
- python-dotenv
  - .env 로드에 사용됩니다.
- openai
  - GPT 기반 맞춤법 교정에 사용됩니다.
- py-hanspell
  - 한국어 맞춤법 교정 대체 엔진으로 사용됩니다.

### 3.2 상수와 기본 경로

extract_and_check.py 는 아래 기본 경로를 코드 내 상수로 정의합니다.

- DEFAULT_ENV_FILE = 현재 파일과 같은 폴더의 .env
- DEFAULT_CONFIG_FILE = 현재 파일과 같은 폴더의 videos.json
- DEFAULT_GENERATED_DIR = 현재 파일과 같은 폴더의 generated
- DEFAULT_ANDROID_ASSETS_DIR = MathChatbotAndroid/app/src/main/assets
- DEFAULT_TRANSCRIPT_LANGUAGES = ["ko", "en"]

즉 기본 실행 시 한국어 우선, 영어 보조 순서로 자막을 요청하고 결과를 generated 및 Android assets 폴더에 동시에 기록합니다.

### 3.3 데이터 모델

파이프라인 내부에서 사용되는 명시적 데이터 모델은 VideoJob 하나입니다.

- topic
  - 과목명
- source_url
  - 원본 YouTube URL
- video_id
  - URL에서 추출한 11자리 영상 ID

이 모델은 배치 처리와 단일 영상 처리 모두에서 동일하게 사용됩니다.

### 3.4 처리 흐름

main() 의 실제 실행 흐름은 다음 순서입니다.

1. parse_args() 로 CLI 인자를 읽습니다.
2. load_dotenv(args.env_file) 로 환경 변수를 주입합니다.
3. --proxy-mode, --proxy-host, --proxy-port 가 들어오면 os.environ 값을 덮어씁니다.
4. build_transcript_api() 로 YouTubeTranscriptApi 인스턴스를 생성합니다.
5. --single 이면 단일 영상 처리, 아니면 videos.json 기반 배치 처리를 수행합니다.
6. 처리 결과를 generated/app_assets/math_topics.json 과 Android assets 폴더에 저장합니다.

### 3.5 핵심 함수 설명

#### extract_video_id(video_input)

역할:
- YouTube URL 또는 이미 분리된 videoId 에서 최종 videoId 를 추출합니다.

지원 형식:
- https://www.youtube.com/watch?v=...
- https://youtu.be/...
- https://www.youtube.com/shorts/...
- https://www.youtube.com/embed/...
- https://www.youtube.com/live/...
- 11자리 videoId 문자열 자체

유효하지 않은 입력이면 ValueError 를 발생시킵니다.

#### sanitize_path_name(name)

역할:
- Windows 경로에서 문제가 되는 문자 \ / : * ? " < > | 를 밑줄로 치환합니다.

용도:
- generated/topics/<과목명>/ 경로를 안전하게 만들기 위해 사용됩니다.

#### build_transcript_api(proxy_mode)

역할:
- 프록시 설정에 따라 YouTubeTranscriptApi 객체를 만듭니다.

지원 모드:
- none
  - 프록시 없이 직접 연결
- generic
  - WEBSHARE_PROXY_HOST, WEBSHARE_PROXY_PORT 를 포함한 일반 HTTP 프록시 URL 구성
- webshare
  - WebshareProxyConfig 사용

동작 특징:
- proxy_mode 가 직접 전달되지 않으면 YTT_PROXY_MODE 환경 변수를 읽습니다.
- generic, webshare 모두 사용자명과 비밀번호가 없으면 RuntimeError 를 발생시킵니다.

#### transcript_to_text(snippets)

역할:
- youtube-transcript-api 가 반환한 스니펫 객체 리스트에서 text 값만 모아 줄바꿈 문자열로 합칩니다.

용도:
- 원문 transcript.txt 와 맞춤법 교정 입력의 공통 원본을 생성합니다.

#### split_text_for_spellcheck(text, max_length)

역할:
- 긴 자막 텍스트를 맞춤법 교정 엔진이 처리하기 쉬운 청크로 나눕니다.

특징:
- 빈 줄은 제거합니다.
- 줄 단위로 누적하다가 max_length 를 넘기면 새 청크를 시작합니다.
- hanspell 기본 청크 길이는 450, GPT 는 1200 을 사용합니다.

#### run_hanspell_spell_check(text, language_code)

역할:
- 한국어 자막일 때만 hanspell 기반 교정을 수행합니다.

동작 규칙:
- language_code 가 ko 로 시작하지 않으면 교정을 건너뜁니다.
- hanspell 라이브러리가 없으면 교정을 건너뜁니다.
- 반환값은 (교정 텍스트, 메타데이터) 튜플입니다.

#### run_gpt_spell_check(text, language_code)

역할:
- OpenAI Responses API 로 한국어 자막의 오탈자, 띄어쓰기, 문장부호를 교정합니다.

동작 규칙:
- 한국어가 아니면 교정을 하지 않습니다.
- openai 패키지가 없거나 OPENAI_API_KEY 가 없으면 교정을 실패로 처리합니다.
- OPENAI_MODEL 이 없으면 기본값 gpt-4o 를 사용합니다.
- chunk 별로 응답을 받아 합친 뒤 최종 교정 텍스트를 만듭니다.

프롬프트 제약:
- 의미를 바꾸지 말 것
- 오탈자, 띄어쓰기, 문장부호만 교정할 것
- 설명 없이 교정된 본문만 반환할 것

#### run_spell_check(text, language_code, engine)

역할:
- 맞춤법 교정 엔진 선택 분기 함수입니다.

지원 엔진:
- none
- gpt
- hanspell
- auto

세부 규칙:
- gpt 지정 시 GPT 교정이 적용되지 않으면 RuntimeError 를 발생시킵니다.
- auto 는 GPT 를 먼저 시도하고 실패하면 hanspell 로 폴백합니다.

#### build_video_payload(job, transcript, transcript_text, checked_text, spellcheck_meta)

역할:
- 앱과 리포트가 공통으로 사용할 영상 단위 데이터 구조를 만듭니다.

주요 필드:
- topic
- displayTitle
- sourceUrl
- videoId
- language
- languageCode
- isGenerated
- spellcheck
- snippetCount
- searchText
- transcriptText
- checkedText
- snippets

중요 포인트:
- spellcheck.applied 가 true 이면 searchText 는 checkedText 를 사용합니다.
- 그렇지 않으면 원문 transcriptText 를 사용합니다.
- 즉 Android 검색 정확도는 교정 성공 여부에 직접 영향을 받습니다.

#### save_video_outputs(base_output_dir, payload)

역할:
- 영상 단위 산출물을 파일로 저장합니다.

생성 파일:
- transcript.json
- transcript.txt
- transcript_checked.txt
- report.json

report.json 에는 스니펫 전체 대신 메타데이터만 들어갑니다.

#### write_combined_outputs(generated_dir, topics, android_assets_dir)

역할:
- 앱이 읽는 통합 JSON 을 생성하고 필요하면 Android assets 폴더로 복사합니다.

출력 구조:
- generatedAt
- topicCount
- videoCount
- topics

파일 경로:
- generated/app_assets/math_topics.json
- MathChatbotAndroid/app/src/main/assets/math_topics.json

#### load_video_jobs(config_path)

역할:
- videos.json 에서 배치 작업 목록을 읽어 VideoJob 리스트로 변환합니다.

주의점:
- urls 가 문자열 하나여도 내부에서 리스트로 정규화합니다.
- topic 이 비어 있거나 URL 이 비어 있으면 해당 항목은 건너뜁니다.

#### process_single_video(...)

역할:
- 자막 fetch, 텍스트 생성, 맞춤법 교정, payload 생성, 파일 저장까지 영상 1개 전체를 담당합니다.

실질적으로 파이프라인의 핵심 처리 단위입니다.

#### process_batch(...)

역할:
- 여러 VideoJob 을 순회하면서 process_single_video() 를 호출하고 topic 별로 묶어서 결합 JSON 을 만듭니다.

출력 로그:
- 처리 중: <과목> / <원본 URL>
- 과목 수: N
- 영상 수: N

### 3.6 CLI 인자

parse_args() 에 정의된 주요 옵션은 다음과 같습니다.

- --url
  - 단일 실행 시 대상 YouTube URL 또는 videoId
- --config
  - 배치 입력 JSON 경로
- --generated-dir
  - 생성 결과 저장 폴더
- --android-assets-dir
  - 앱 assets 출력 폴더
- --env-file
  - .env 경로
- --single
  - 단일 영상 실행 모드
- --proxy-mode
  - none | webshare | generic
- --proxy-host
  - generic 프록시 호스트
- --proxy-port
  - generic 프록시 포트
- --spellcheck-engine
  - gpt | hanspell | auto | none

### 3.7 입력 파일 형식

videos.json 은 아래 구조를 사용합니다.

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

subjects 배열의 각 항목은 과목명 name 과 URL 배열 urls 를 가져야 합니다.

### 3.8 생성 산출물 형식

영상 단위 폴더는 아래 구조를 갖습니다.

```text
generated/topics/<과목명>/<videoId>/
  transcript.json
  transcript.txt
  transcript_checked.txt
  report.json
```

통합 자산은 아래 구조입니다.

```json
{
  "generatedAt": "2026-04-14T...Z",
  "topicCount": 1,
  "videoCount": 1,
  "topics": [
    {
      "name": "벡터",
      "videos": [
        {
          "topic": "벡터",
          "displayTitle": "벡터",
          "sourceUrl": "https://www.youtube.com/watch?v=...",
          "videoId": "Fh9vBLIcuj4",
          "searchText": "...",
          "snippets": [
            {
              "text": "...",
              "start": 12.3,
              "duration": 5.4
            }
          ]
        }
      ]
    }
  ]
}
```

Android 앱은 이 JSON 중 topics, videos, snippets, searchText, sourceUrl, topic 필드를 핵심적으로 사용합니다.

### 3.9 환경 변수

파이프라인 및 교정 로직은 다음 환경 변수를 사용합니다.

- YTT_PROXY_MODE
- WEBSHARE_PROXY_USERNAME
- WEBSHARE_PROXY_PASSWORD
- WEBSHARE_PROXY_HOST
- WEBSHARE_PROXY_PORT
- OPENAI_API_KEY
- OPENAI_MODEL

OPENAI_API_KEY, 프록시 사용자명, 프록시 비밀번호는 민감 정보이므로 문서나 Git 커밋에 포함하면 안 됩니다.

## 4. Android 앱 상세

### 4.1 소스 파일 구조

핵심 Kotlin 파일은 3개입니다.

- MainActivity.kt
  - 앱의 화면 제어, 자산 로드, 검색, 메시지 표시를 전부 담당합니다.
- ChatAdapter.kt
  - RecyclerView 어댑터로 사용자 메시지와 봇 메시지 뷰를 바인딩합니다.
- ChatMessage.kt
  - text 와 isUser 두 필드를 가진 단순 데이터 클래스입니다.

### 4.2 MainActivity 내부 데이터 클래스

MainActivity 는 화면 내부에서만 사용할 데이터 구조를 중첩 data class 로 선언합니다.

- Snippet
  - text, start, duration 보유
- VideoEntry
  - topic, displayTitle, sourceUrl, videoId, searchText, snippets 보유
- TopicEntry
  - name, videos 보유
- SearchMatch
  - topic, sourceUrl, snippet, score 보유

즉 JSON 파싱 결과를 앱 내부용 객체로 다시 매핑한 뒤 검색에 사용합니다.

### 4.3 화면 초기화 흐름

onCreate() 의 흐름은 다음과 같습니다.

1. activity_main 레이아웃을 inflate 합니다.
2. 제목, RecyclerView, 입력창, 전송 버튼, 과목 칩 그룹 뷰를 바인딩합니다.
3. ChatAdapter 와 LinearLayoutManager 를 연결합니다.
4. assets 의 math_topics.json 을 loadTopics() 로 읽습니다.
5. renderTopicChips() 로 과목 칩을 구성합니다.
6. buildIntroMessage() 로 초기 안내 메시지를 추가합니다.
7. 전송 버튼과 IME 전송 액션에 sendMessage() 를 연결합니다.

### 4.4 JSON 로딩 로직

loadTopics() 는 assets.open("math_topics.json") 으로 JSON 파일을 읽고 JSONObject/JSONArray 기반으로 파싱합니다.

파싱 특징:
- 예외 발생 시 앱이 크래시하지 않고 emptyList() 를 반환합니다.
- 각 topic 의 videos 배열을 순회합니다.
- 각 video 의 snippets 배열을 순회해 Snippet 객체 리스트를 만듭니다.
- 최종적으로 TopicEntry 리스트를 반환합니다.

이 구조 때문에 자산 파일이 없거나 파싱에 실패하면 앱은 빈 데이터 상태로 시작합니다.

### 4.5 과목 칩 렌더링

renderTopicChips() 는 항상 첫 칩으로 전체 를 추가하고, 이후 topic.name 을 기준으로 과목별 칩을 생성합니다.

addTopicChip(label, topicName, isChecked) 의 동작:
- item_topic_chip.xml 을 inflate 합니다.
- chip.text 와 chip.isChecked 값을 설정합니다.
- 클릭 시 selectedTopic 값을 갱신합니다.
- 검색 범위 변경 안내 봇 메시지를 추가합니다.

전체 칩은 selectedTopic = null 을 의미하고, 특정 과목 칩은 해당 과목명으로 검색 범위를 제한합니다.

### 4.6 안내 메시지 생성

buildIntroMessage() 는 앱 시작 시 보여줄 고정 안내 문구를 만듭니다.

분기:
- topics 가 비어 있으면 파이프라인을 먼저 실행하라는 메시지를 보여줍니다.
- 데이터가 있으면 과목 목록을 쉼표로 연결해 현재 로드된 과목을 보여줍니다.

### 4.7 메시지 전송 흐름

sendMessage() 의 처리 순서는 다음과 같습니다.

1. 입력값을 trim 합니다.
2. 빈 문자열이면 바로 종료합니다.
3. 사용자 메시지를 RecyclerView 에 추가합니다.
4. 입력창을 비웁니다.
5. 키보드를 내립니다.
6. searchInTopics(query) 결과를 봇 메시지로 추가합니다.

즉 이 앱은 서버 호출 없이 UI 스레드에서 즉시 검색 결과를 계산합니다.

### 4.8 검색 알고리즘

searchInTopics(query) 는 규칙 기반 점수 합산 방식으로 동작합니다.

전처리:
- tokenize(query) 로 토큰 목록 생성
- 토큰 길이가 2글자 미만이면 제거
- 공백 제거 후 normalize() 로 소문자화 및 특수문자 제거

후보 선정:
- selectedTopic 이 null 이면 전체 과목의 videos 사용
- 아니면 선택 과목의 videos 만 사용

점수 계산 규칙:
- token 이 video.searchText 에 포함되면 +2
- token 이 snippet.text 에 포함되면 +5
- token 이 video.topic 에 포함되면 +3

결과 처리:
- score > 0 인 스니펫만 후보로 남깁니다.
- score 내림차순, snippet.start 오름차순으로 정렬합니다.
- 상위 3개만 응답에 포함합니다.

반환 문장 형식:
- 질문 원문
- 관련 자막 구간 제목
- 과목명
- MM:SS 타임스탬프
- 자막 원문
- 클릭 가능한 링크

### 4.9 문자열 정규화와 토큰화

normalize(value) 는 아래 규칙을 적용합니다.

- lowercase()
- 정규식 [^\p{L}\p{N}] 제거

즉 한글, 영문, 숫자만 남기고 공백과 문장부호를 제거합니다.

tokenize(query) 는 두 가지 종류의 토큰을 생성합니다.

1. 전체 문장을 normalize 한 결합 토큰
2. 공백 기준 분리 후 길이 2 이상인 개별 토큰

이 방식은 "벡터 내적" 같은 다중 단어 질문에서 결합 매칭과 개별 단어 매칭을 모두 허용하기 위한 구현입니다.

### 4.10 링크 생성

buildTimestampUrl(sourceUrl, startSeconds) 는 기존 URL 에서 t 파라미터를 제거한 뒤 새로운 t=<초>s 값을 붙입니다.

예:
- 원본 URL: https://www.youtube.com/watch?v=abc123&t=40s
- 스니펫 시작 초: 143
- 결과 URL: https://www.youtube.com/watch?v=abc123&t=143s

초 값은 startSeconds.toInt() 로 버림 처리합니다.

### 4.11 메시지 렌더링

ChatAdapter 는 사용자 메시지와 봇 메시지에 따라 서로 다른 레이아웃을 사용합니다.

- 사용자 메시지
  - item_message_user.xml
  - 오른쪽 정렬
  - user_bubble_bg 사용
- 봇 메시지
  - item_message_bot.xml
  - 왼쪽 정렬
  - bot_bubble_bg 사용
  - Linkify.WEB_URLS 적용

ChatAdapter.MessageViewHolder.bind(message) 는 봇 메시지일 때만 URL 자동 링크와 LinkMovementMethod 를 켭니다.

### 4.12 레이아웃 및 리소스

activity_main.xml 구성:
- 상단 제목 TextView
- 설명 문구 TextView
- 가로 스크롤 가능한 ChipGroup
- 대화 목록 RecyclerView
- 하단 입력창 + 전송 버튼

문자열 리소스:
- app_name = 수학 자막 챗봇
- send = 보내기

이 앱은 비교적 작은 단일 화면 구조이며, Fragment 나 ViewModel 없이 Activity 하나에 로직이 집중되어 있습니다.

## 5. Android 빌드 설정

MathChatbotAndroid/app/build.gradle 기준 설정은 다음과 같습니다.

- namespace = com.example.mathchatbot
- applicationId = com.example.mathchatbot
- compileSdk = 34
- minSdk = 26
- targetSdk = 34
- versionCode = 2
- versionName = 1.1
- Java/Kotlin target = 11

의존성:
- androidx.core.ktx
- androidx.appcompat
- material
- androidx.activity
- androidx.constraintlayout
- androidx.recyclerview

### 5.1 릴리즈 서명 처리

build.gradle 은 readSecret 클로저를 통해 먼저 local.properties, 그다음 환경 변수에서 값을 읽습니다.

대상 키:
- RELEASE_STORE_FILE
- RELEASE_KEY_ALIAS
- RELEASE_STORE_PASSWORD
- RELEASE_KEY_PASSWORD

규칙:
- 4개가 모두 있으면 signingConfigs.release 를 구성합니다.
- 하나라도 없으면 unsigned release APK 를 빌드합니다.
- 이때 콘솔에 unsigned release 빌드 안내를 출력합니다.

즉 서명 정보가 없는 환경에서도 assembleRelease 자체는 실패하지 않도록 설계되어 있습니다.

## 6. 실행 명령 예시

### 6.1 전체 배치 처리

```powershell
cd c:/Users/User/vibeCoding/YOUTUBE/MATH
& "c:/Users/User/vibeCoding/.venv/Scripts/python.exe" extract_and_check.py --proxy-mode none --spellcheck-engine gpt
```

### 6.2 단일 영상 테스트

```powershell
cd c:/Users/User/vibeCoding/YOUTUBE/MATH
& "c:/Users/User/vibeCoding/.venv/Scripts/python.exe" extract_and_check.py --single --url "https://www.youtube.com/watch?v=VIDEO_ID" --proxy-mode none --spellcheck-engine none
```

### 6.3 Android 디버그 빌드

```powershell
cd c:/Users/User/vibeCoding/YOUTUBE/MATH/MathChatbotAndroid
./gradlew.bat assembleDebug
```

### 6.4 Android 릴리즈 빌드

```powershell
cd c:/Users/User/vibeCoding/YOUTUBE/MATH/MathChatbotAndroid
./gradlew.bat assembleRelease
```

## 7. 유지보수 관점의 주의점

### 7.1 Python 파이프라인 쪽

- gpt 엔진은 OPENAI_API_KEY 가 없으면 실패합니다.
- auto 엔진은 GPT 실패 시 hanspell 로 폴백합니다.
- gpt 엔진을 명시했을 때 GPT 가 적용되지 않으면 예외가 발생하도록 의도돼 있습니다.
- searchText 는 교정 결과를 사용하므로 교정 품질이 앱 검색 결과에 직접 반영됩니다.

### 7.2 Android 앱 쪽

- MainActivity 하나에 파싱, 상태, 검색, UI 제어가 집중돼 있어 기능이 커지면 분리가 필요합니다.
- 현재 검색은 단순 포함 매칭 기반이라 동의어, 오탈자, 문맥 이해는 약합니다.
- assets JSON 파싱 실패 시 조용히 emptyList() 를 반환하므로 디버깅 시 파일 존재 여부와 JSON 구조를 먼저 확인해야 합니다.

### 7.3 보안 및 Git 관리

- .env, local.properties 의 민감 정보는 커밋하면 안 됩니다.
- keystore 파일과 RELEASE_* 비밀번호도 저장소에 넣으면 안 됩니다.
- generated/ 는 재생성 가능한 산출물이므로 필요 시 다시 만들 수 있습니다.

## 8. 확장 포인트

실제 코드 기준으로 확장하기 좋은 지점은 다음과 같습니다.

1. 검색 품질 개선
- searchInTopics() 를 BM25, 형태소 분석, 임베딩 검색으로 교체 가능

2. 구조 분리
- MainActivity 의 JSON 파싱과 검색 로직을 별도 클래스 또는 ViewModel 로 이동 가능

3. 메타데이터 확장
- build_video_payload() 에 난이도, 강의자, 단원, 썸네일 같은 필드 추가 가능

4. 자막 후처리 강화
- GPT 교정 이후 문단화, 중복 제거, 용어 통일 단계 추가 가능

5. 다과목 앱 일반화
- math_topics.json 파일명을 과목별 설정값으로 외부화하면 다른 교과 앱으로 재사용 가능

## 9. 요약

이 프로젝트의 핵심은 extract_and_check.py 가 YouTube 자막을 수집하고 교정하여 math_topics.json 을 생성하고, Android 앱이 그 JSON 을 로컬에서 검색해 대화형 결과를 보여주는 구조입니다.

즉 소스코드 관점에서 가장 중요한 연결점은 아래 한 줄로 요약됩니다.

videos.json -> extract_and_check.py -> generated/app_assets/math_topics.json -> MathChatbotAndroid/app/src/main/assets/math_topics.json -> MainActivity.searchInTopics()
