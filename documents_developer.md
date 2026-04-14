# MATH 개발자 API 문서

## 시스템 흐름

- 파이프라인: videos.json -> extract_and_check.py -> generated/app_assets/math_topics.json
- 앱: app/src/main/assets/math_topics.json 로드 -> 로컬 검색 -> 결과 링크 출력

핵심 연결점:
- Python이 생성한 searchText, snippets, sourceUrl 필드를 Android가 그대로 소비합니다.
- 교정 결과가 searchText 로 들어가므로 검색 품질은 파이프라인 단계에서 결정됩니다.

## Python API

대상 파일: extract_and_check.py

### 데이터 모델

#### VideoJob

역할:
- 영상 1개 처리 단위를 표현하는 dataclass

필드:
- topic: 과목명
- source_url: 원본 YouTube URL
- video_id: 추출된 영상 ID

### 유틸리티 함수

#### extract_video_id(video_input: str) -> str

역할:
- YouTube URL 또는 11자리 videoId 입력에서 최종 videoId 를 추출

지원 입력:
- watch URL
- youtu.be 단축 URL
- shorts URL
- embed URL
- live URL
- 11자리 videoId 문자열

예외:
- 유효한 형식이 아니면 ValueError 발생

#### sanitize_path_name(name: str) -> str

역할:
- 파일 시스템에 안전한 폴더명으로 정규화

세부 동작:
- Windows 금지 문자 \ / : * ? " < > | 를 _ 로 치환
- 빈 문자열이면 untitled 반환

#### transcript_to_text(snippets: Iterable[object]) -> str

역할:
- transcript 스니펫 리스트를 줄바꿈 문자열로 변환

입력 기대값:
- 각 요소가 text 속성을 가져야 함

#### split_text_for_spellcheck(text: str, max_length: int = 450) -> list[str]

역할:
- 긴 텍스트를 맞춤법 교정용 청크로 분할

규칙:
- 빈 줄 제거
- 줄 단위 누적
- max_length 초과 시 새 청크 시작

### 자막 API 및 프록시

#### build_transcript_api(proxy_mode: str | None = None) -> YouTubeTranscriptApi

역할:
- 프록시 설정을 반영한 YouTubeTranscriptApi 인스턴스 생성

지원 모드:
- none: 프록시 없이 직접 연결
- generic: GenericProxyConfig 사용
- webshare: WebshareProxyConfig 사용

환경 변수:
- YTT_PROXY_MODE
- WEBSHARE_PROXY_USERNAME
- WEBSHARE_PROXY_PASSWORD
- WEBSHARE_PROXY_HOST
- WEBSHARE_PROXY_PORT

실패 조건:
- generic 또는 webshare 에 필요한 값이 없으면 RuntimeError 발생

### 맞춤법 교정 API

#### run_hanspell_spell_check(text: str, language_code: str) -> tuple[str, dict[str, object]]

역할:
- 한국어 자막에 대해 py-hanspell 교정 수행

반환값:
- 1번째 값: 교정된 텍스트 또는 원문
- 2번째 값: applied, reason 을 포함한 메타데이터

건너뛰는 조건:
- language_code 가 ko 로 시작하지 않음
- hanspell 패키지가 설치되지 않음

#### run_gpt_spell_check(text: str, language_code: str) -> tuple[str, dict[str, object]]

역할:
- OpenAI Responses API 기반 한국어 자막 교정 수행

환경 변수:
- OPENAI_API_KEY
- OPENAI_MODEL, 기본값 gpt-4o

동작 특징:
- max_length 1200 기준으로 청크 분할
- 청크별로 교정 후 합침
- 의미 변경 없이 오탈자, 띄어쓰기, 문장부호만 교정하도록 지시

건너뛰는 조건:
- 한국어 자막이 아님
- openai 패키지가 없음
- OPENAI_API_KEY 가 없음

#### run_spell_check(text: str, language_code: str, engine: str) -> tuple[str, dict[str, object]]

역할:
- 맞춤법 교정 엔진 선택 진입점

지원 엔진:
- none
- gpt
- hanspell
- auto

중요 동작:
- gpt 지정 시 GPT 적용 실패를 허용하지 않고 RuntimeError 발생
- auto 지정 시 GPT 먼저 시도 후 실패하면 hanspell 폴백

### 데이터 생성 API

#### build_video_payload(job: VideoJob, transcript: object, transcript_text: str, checked_text: str, spellcheck_meta: dict[str, object]) -> dict[str, object]

역할:
- 앱과 리포트에서 사용할 영상 단위 JSON 객체 생성

주요 출력 필드:
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

중요 규칙:
- spellcheck.applied 가 true 면 searchText 에 checkedText 저장
- 아니면 transcriptText 저장

#### save_video_outputs(base_output_dir: Path, payload: dict[str, object]) -> None

역할:
- 영상별 산출물을 디스크에 저장

생성 파일:
- transcript.json
- transcript.txt
- transcript_checked.txt
- report.json

저장 위치:
- generated/topics/<topic>/<videoId>/...

#### write_combined_outputs(generated_dir: Path, topics: list[dict[str, object]], android_assets_dir: Path | None) -> None

역할:
- 앱용 통합 JSON 생성 및 Android assets 동기화

생성 파일:
- generated/app_assets/math_topics.json
- MathChatbotAndroid/app/src/main/assets/math_topics.json

최상위 필드:
- generatedAt
- topicCount
- videoCount
- topics

#### load_video_jobs(config_path: Path) -> list[VideoJob]

역할:
- videos.json 을 읽어 VideoJob 리스트 생성

허용 입력:
- urls 는 배열 또는 문자열 1개 모두 허용

제외 조건:
- topic 이 비어 있음
- URL 이 비어 있음

#### process_single_video(ytt_api: YouTubeTranscriptApi, job: VideoJob, base_output_dir: Path, spellcheck_engine: str) -> dict[str, object]

역할:
- 영상 1개 전체 처리

처리 단계:
- 자막 fetch
- 원문 텍스트 생성
- 맞춤법 교정
- payload 생성
- 파일 저장

#### process_batch(ytt_api: YouTubeTranscriptApi, jobs: list[VideoJob], generated_dir: Path, android_assets_dir: Path | None, spellcheck_engine: str) -> None

역할:
- 여러 영상을 순회 처리하고 topic 단위로 묶어 통합 JSON 생성

출력 로그:
- 처리 중: <topic> / <url>
- 과목 수: N
- 영상 수: N

### CLI API

#### parse_args() -> argparse.Namespace

지원 옵션:
- --url
- --config
- --generated-dir
- --android-assets-dir
- --env-file
- --single
- --proxy-mode
- --proxy-host
- --proxy-port
- --spellcheck-engine

#### main() -> None

역할:
- 환경 변수 로드, 인자 반영, API 초기화, 단일 또는 배치 실행 분기 처리

실행 분기:
- --single 이면 generated/single 아래로 출력
- 기본값이면 videos.json 배치 처리

## Android API

대상 파일:
- MainActivity.kt
- ChatAdapter.kt
- ChatMessage.kt

### 데이터 클래스

#### ChatMessage

필드:
- text: 메시지 본문
- isUser: 사용자 메시지 여부

#### MainActivity.Snippet

필드:
- text
- start
- duration

#### MainActivity.VideoEntry

필드:
- topic
- displayTitle
- sourceUrl
- videoId
- searchText
- snippets

#### MainActivity.TopicEntry

필드:
- name
- videos

#### MainActivity.SearchMatch

필드:
- topic
- sourceUrl
- snippet
- score

### 화면 초기화 API

#### onCreate(savedInstanceState: Bundle?)

역할:
- 레이아웃 바인딩, RecyclerView 초기화, 자산 로드, 과목 칩 생성, 초기 메시지 출력, 이벤트 연결

초기화 대상 뷰:
- titleText
- recyclerView
- editText
- sendButton
- subjectChipGroup

#### loadTopics() -> List<TopicEntry>

역할:
- assets 의 math_topics.json 파싱

입력 원천:
- assets.open("math_topics.json")

실패 처리:
- 예외 발생 시 emptyList() 반환

#### renderTopicChips() -> Unit

역할:
- 전체 칩과 과목별 칩을 ChipGroup 에 렌더링

#### addTopicChip(label: String, topicName: String?, isChecked: Boolean) -> Unit

역할:
- Chip 하나를 생성하고 클릭 동작을 연결

클릭 결과:
- selectedTopic 갱신
- 범위 변경 안내 봇 메시지 추가
- 스크롤 갱신

#### buildIntroMessage() -> String

역할:
- 앱 시작 시 보여줄 안내 메시지 생성

분기:
- topics 가 비어 있으면 파이프라인 실행 안내
- 아니면 현재 과목 목록 표시

### 검색 API

#### sendMessage() -> Unit

역할:
- 입력값 검증, 사용자 메시지 추가, 키보드 숨김, 검색 결과 메시지 추가

#### searchInTopics(query: String) -> String

역할:
- 로컬 자막 검색의 핵심 함수

전처리:
- tokenize(query)
- 선택 과목 필터 적용

점수 규칙:
- token in searchText: +2
- token in snippet.text: +5
- token in topic: +3

정렬 규칙:
- score 내림차순
- snippet.start 오름차순

반환값:
- 상위 3개 스니펫을 포함한 문자열 응답

#### tokenize(query: String) -> List<String>

역할:
- 검색용 토큰 생성

규칙:
- 전체 문장 normalize 결과를 토큰으로 추가
- 공백 분리 후 길이 2 이상 토큰 추가
- 중복 제거

#### normalize(value: String) -> String

역할:
- 검색 비교용 정규화

규칙:
- lowercase
- 한글, 영문, 숫자를 제외한 문자 제거

#### formatTimestamp(seconds: Double) -> String

역할:
- 초 단위를 MM:SS 문자열로 변환

#### buildTimestampUrl(sourceUrl: String, startSeconds: Double) -> String

역할:
- 기존 t 파라미터를 제거하고 새 타임스탬프 링크 생성

출력 예:
- https://www.youtube.com/watch?v=...&t=143s

### 메시지 렌더링 API

#### addUserMessage(text: String) -> Unit

역할:
- 사용자 메시지를 목록에 추가하고 RecyclerView 갱신

#### addBotMessage(text: String) -> Unit

역할:
- 봇 메시지를 목록에 추가하고 RecyclerView 갱신

#### refreshScroll() -> Unit

역할:
- 최신 메시지로 스크롤 이동

#### ChatAdapter.onCreateViewHolder(parent: ViewGroup, viewType: Int) -> MessageViewHolder

역할:
- 사용자/봇 메시지 타입에 맞는 레이아웃 inflate

레이아웃 매핑:
- 1 -> item_message_user
- 2 -> item_message_bot

#### ChatAdapter.onBindViewHolder(holder: MessageViewHolder, position: Int) -> Unit

역할:
- 지정 위치 메시지를 ViewHolder 에 바인딩

#### ChatAdapter.getItemViewType(position: Int) -> Int

역할:
- isUser 값에 따라 메시지 타입 반환

#### ChatAdapter.MessageViewHolder.bind(message: ChatMessage) -> Unit

역할:
- 텍스트 바인딩
- 봇 메시지일 때 Linkify.WEB_URLS 및 LinkMovementMethod 적용

## 자주 쓰는 명령

```powershell
# 데이터 생성
cd c:/Users/User/vibeCoding/YOUTUBE/MATH
& "c:/Users/User/vibeCoding/.venv/Scripts/python.exe" extract_and_check.py --proxy-mode none --spellcheck-engine gpt

# 단일 영상 테스트
cd c:/Users/User/vibeCoding/YOUTUBE/MATH
& "c:/Users/User/vibeCoding/.venv/Scripts/python.exe" extract_and_check.py --single --url "https://www.youtube.com/watch?v=VIDEO_ID" --proxy-mode none --spellcheck-engine none

# 앱 릴리즈 빌드
cd c:/Users/User/vibeCoding/YOUTUBE/MATH/MathChatbotAndroid
$env:JAVA_HOME='C:/Program Files/Android/Android Studio/jbr'
./gradlew.bat assembleRelease
```

## 빠른 점검 포인트

- 교정 미적용: OPENAI_API_KEY, report.json 의 spellcheck.reason 확인
- 검색 결과 부족: math_topics.json 생성 여부, assets 복사 여부, searchText 내용 확인
- 링크 이상: sourceUrl 의 기존 t 파라미터 제거 여부와 buildTimestampUrl 결과 확인
- 앱 데이터 없음: loadTopics() 예외 여부와 assets 파일 구조 확인

## 빌드 메모

- versionCode 는 릴리즈마다 1씩 증가
- versionName 은 태그와 맞추는 편이 관리에 유리
- RELEASE_* 4개가 모두 없으면 unsigned release 빌드
- local.properties 또는 환경 변수에서 서명값을 읽음

## 운영 원칙

- .env, keystore, 비밀번호는 커밋 금지
- generated 는 재생성 가능한 산출물
- 앱은 오프라인 우선 구조 유지
