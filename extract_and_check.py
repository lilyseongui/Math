from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import GenericProxyConfig, WebshareProxyConfig

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    from hanspell import spell_checker
except ImportError:
    spell_checker = None


DEFAULT_URL = "https://www.youtube.com/watch?v=5shf9ab9nGE"
DEFAULT_ENV_FILE = Path(__file__).with_name(".env")
DEFAULT_CONFIG_FILE = Path(__file__).with_name("videos.json")
DEFAULT_GENERATED_DIR = Path(__file__).with_name("generated")
DEFAULT_ANDROID_ASSETS_DIR = (
    Path(__file__).with_name("MathChatbotAndroid") / "app" / "src" / "main" / "assets"
)
DEFAULT_TRANSCRIPT_LANGUAGES = ["ko", "en"]
PROXY_MODE_ENV = "YTT_PROXY_MODE"
PROXY_USERNAME_ENV = "WEBSHARE_PROXY_USERNAME"
PROXY_PASSWORD_ENV = "WEBSHARE_PROXY_PASSWORD"
PROXY_HOST_ENV = "WEBSHARE_PROXY_HOST"
PROXY_PORT_ENV = "WEBSHARE_PROXY_PORT"
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
OPENAI_MODEL_ENV = "OPENAI_MODEL"


@dataclass
class VideoJob:
    topic: str
    source_url: str
    video_id: str


def extract_video_id(video_input: str) -> str:
    parsed = urlparse(video_input)
    if parsed.scheme and parsed.netloc:
        if parsed.netloc in {"youtu.be", "www.youtu.be"}:
            return parsed.path.strip("/")

        if "youtube.com" in parsed.netloc:
            query_video_id = parse_qs(parsed.query).get("v", [None])[0]
            if query_video_id:
                return query_video_id

            path_parts = [part for part in parsed.path.split("/") if part]
            if len(path_parts) >= 2 and path_parts[0] in {"shorts", "embed", "live"}:
                return path_parts[1]

    if re.fullmatch(r"[A-Za-z0-9_-]{11}", video_input):
        return video_input

    raise ValueError("유효한 유튜브 URL 또는 비디오 ID를 입력해야 합니다.")


def sanitize_path_name(name: str) -> str:
    normalized = re.sub(r"[\\/:*?\"<>|]", "_", name.strip())
    return normalized or "untitled"


def build_transcript_api(proxy_mode: str | None = None) -> YouTubeTranscriptApi:
    """
    proxy_mode 값에 따라 YouTubeTranscriptApi 인스턴스를 반환합니다.
      - "none"     : 프록시 없이 직접 연결 (YouTubeTranscriptApi())
      - "generic"  : GenericProxyConfig(http_url, https_url) 사용
      - "webshare" : WebshareProxyConfig(proxy_username, proxy_password) 사용
                     ※ Webshare "Residential" 요금제만 지원됩니다.
                       (Proxy Server / Static Residential 불가)
    """
    if proxy_mode is None:
        proxy_mode = os.getenv(PROXY_MODE_ENV, "none").strip().lower()

    # 프록시 없이 직접 연결
    if proxy_mode == "none":
        return YouTubeTranscriptApi()

    proxy_username = os.getenv(PROXY_USERNAME_ENV)
    proxy_password = os.getenv(PROXY_PASSWORD_ENV)

    if not proxy_username or not proxy_password:
        raise RuntimeError(
            f"프록시 정보가 없습니다. {PROXY_USERNAME_ENV} 와 {PROXY_PASSWORD_ENV} 를 설정하세요."
        )

    if proxy_mode == "generic":
        proxy_host = os.getenv(PROXY_HOST_ENV)
        proxy_port = os.getenv(PROXY_PORT_ENV)
        if not proxy_host or not proxy_port:
            raise RuntimeError(
                f"Generic 프록시 모드에는 {PROXY_HOST_ENV} 와 {PROXY_PORT_ENV} 가 필요합니다."
            )
        proxy_url = f"http://{proxy_username}:{proxy_password}@{proxy_host}:{proxy_port}"
        return YouTubeTranscriptApi(
            proxy_config=GenericProxyConfig(
                http_url=proxy_url,
                https_url=proxy_url,
            )
        )

    # webshare — Residential 요금제 전용
    return YouTubeTranscriptApi(
        proxy_config=WebshareProxyConfig(
            proxy_username=proxy_username,
            proxy_password=proxy_password,
        )
    )


def transcript_to_text(snippets: Iterable[object]) -> str:
    lines: list[str] = []
    for snippet in snippets:
        text = getattr(snippet, "text", "").strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


def split_text_for_spellcheck(text: str, max_length: int = 450) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_length = 0

    for line in text.splitlines():
        normalized = line.strip()
        if not normalized:
            continue

        projected = current_length + len(normalized) + (1 if current else 0)
        if current and projected > max_length:
            chunks.append(" ".join(current))
            current = [normalized]
            current_length = len(normalized)
            continue

        current.append(normalized)
        current_length = projected

    if current:
        chunks.append(" ".join(current))

    return chunks


def run_hanspell_spell_check(text: str, language_code: str) -> tuple[str, dict[str, object]]:
    if not language_code.lower().startswith("ko"):
        return text, {
            "applied": False,
            "reason": f"한국어 자막이 아니어서 맞춤법 검사를 건너뜀 ({language_code})",
        }

    if spell_checker is None:
        return text, {
            "applied": False,
            "reason": "py-hanspell 이 설치되지 않아 맞춤법 검사를 건너뜀",
        }

    corrected_chunks: list[str] = []
    for chunk in split_text_for_spellcheck(text):
        result = spell_checker.check(chunk)
        corrected_chunks.append(result.checked)

    return "\n\n".join(corrected_chunks), {
        "applied": True,
        "reason": "한국어 자막에 대해 py-hanspell 검사 완료",
    }


def run_gpt_spell_check(text: str, language_code: str) -> tuple[str, dict[str, object]]:
    if not language_code.lower().startswith("ko"):
        return text, {
            "applied": False,
            "reason": f"한국어 자막이 아니어서 GPT 맞춤법 검사를 건너뜀 ({language_code})",
        }

    if OpenAI is None:
        return text, {
            "applied": False,
            "reason": "openai 패키지가 없어 GPT 맞춤법 검사를 실행할 수 없음",
        }

    api_key = os.getenv(OPENAI_API_KEY_ENV)
    if not api_key:
        return text, {
            "applied": False,
            "reason": f"{OPENAI_API_KEY_ENV} 가 없어 GPT 맞춤법 검사를 실행할 수 없음",
        }

    model = os.getenv(OPENAI_MODEL_ENV, "gpt-4o")
    client = OpenAI(api_key=api_key, timeout=60.0)  # 60초 타임아웃

    chunks = split_text_for_spellcheck(text, max_length=1200)
    corrected_chunks: list[str] = []
    for i, chunk in enumerate(chunks, 1):
        print(f"  GPT 맞춤법 검사 청크 {i}/{len(chunks)} ...")
        response = client.responses.create(
            model=model,
            instructions=(
                "당신은 한국어 자막 맞춤법 교정기다. 의미를 바꾸지 말고 오탈자, 띄어쓰기, 문장부호만 교정하라. "
                "설명 없이 교정된 본문만 반환하라."
            ),
            input=chunk,
        )
        corrected_chunks.append(response.output_text.strip())

    return "\n\n".join(corrected_chunks), {
        "applied": True,
        "reason": f"OpenAI {model} 로 한국어 자막 맞춤법 검사 완료",
    }


def run_spell_check(text: str, language_code: str, engine: str) -> tuple[str, dict[str, object]]:
    if engine == "none":
        return text, {
            "applied": False,
            "reason": "맞춤법 검사를 사용하지 않도록 설정됨",
        }

    if engine == "gpt":
        corrected_text, metadata = run_gpt_spell_check(text, language_code)
        if not metadata["applied"]:
            raise RuntimeError(str(metadata["reason"]))
        return corrected_text, metadata

    if engine == "hanspell":
        return run_hanspell_spell_check(text, language_code)

    corrected_text, metadata = run_gpt_spell_check(text, language_code)
    if metadata["applied"]:
        return corrected_text, metadata

    return run_hanspell_spell_check(text, language_code)


def build_video_payload(
    job: VideoJob,
    transcript: object,
    transcript_text: str,
    checked_text: str,
    spellcheck_meta: dict[str, object],
) -> dict[str, object]:
    raw_snippets = transcript.to_raw_data()
    search_text = checked_text if spellcheck_meta["applied"] else transcript_text

    return {
        "topic": job.topic,
        "displayTitle": job.topic,
        "sourceUrl": job.source_url,
        "videoId": transcript.video_id,
        "language": transcript.language,
        "languageCode": transcript.language_code,
        "isGenerated": transcript.is_generated,
        "spellcheck": spellcheck_meta,
        "snippetCount": len(transcript),
        "searchText": search_text,
        "transcriptText": transcript_text,
        "checkedText": checked_text,
        "snippets": raw_snippets,
    }


def save_video_outputs(base_output_dir: Path, payload: dict[str, object]) -> None:
    topic_dir = base_output_dir / sanitize_path_name(str(payload["topic"])) / str(payload["videoId"])
    topic_dir.mkdir(parents=True, exist_ok=True)

    (topic_dir / "transcript.json").write_text(
        json.dumps(payload["snippets"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (topic_dir / "transcript.txt").write_text(str(payload["transcriptText"]), encoding="utf-8")
    (topic_dir / "transcript_checked.txt").write_text(
        str(payload["checkedText"]),
        encoding="utf-8",
    )

    report = {
        "topic": payload["topic"],
        "displayTitle": payload["displayTitle"],
        "sourceUrl": payload["sourceUrl"],
        "videoId": payload["videoId"],
        "language": payload["language"],
        "languageCode": payload["languageCode"],
        "isGenerated": payload["isGenerated"],
        "snippetCount": payload["snippetCount"],
        "spellcheck": payload["spellcheck"],
    }
    (topic_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def write_combined_outputs(
    generated_dir: Path,
    topics: list[dict[str, object]],
    android_assets_dir: Path | None,
) -> None:
    generated_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "topicCount": len(topics),
        "videoCount": sum(len(topic["videos"]) for topic in topics),
        "topics": topics,
    }

    combined_path = generated_dir / "math_topics.json"
    combined_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if android_assets_dir is not None:
        android_assets_dir.mkdir(parents=True, exist_ok=True)
        (android_assets_dir / "math_topics.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def load_video_jobs(config_path: Path) -> list[VideoJob]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    jobs: list[VideoJob] = []
    for subject in config.get("subjects", []):
        topic = str(subject.get("name", "")).strip()
        urls = subject.get("urls", [])
        if isinstance(urls, str):
            urls = [urls]

        for source_url in urls:
            cleaned_url = str(source_url).strip()
            if not topic or not cleaned_url:
                continue
            jobs.append(
                VideoJob(
                    topic=topic,
                    source_url=cleaned_url,
                    video_id=extract_video_id(cleaned_url),
                )
            )
    return jobs


def process_single_video(
    ytt_api: YouTubeTranscriptApi,
    job: VideoJob,
    base_output_dir: Path,
    spellcheck_engine: str,
) -> dict[str, object]:
    transcript = ytt_api.fetch(job.video_id, languages=DEFAULT_TRANSCRIPT_LANGUAGES)
    transcript_text = transcript_to_text(transcript)
    checked_text, spellcheck_meta = run_spell_check(
        transcript_text,
        transcript.language_code,
        spellcheck_engine,
    )
    payload = build_video_payload(job, transcript, transcript_text, checked_text, spellcheck_meta)
    save_video_outputs(base_output_dir, payload)
    return payload


def process_batch(
    ytt_api: YouTubeTranscriptApi,
    jobs: list[VideoJob],
    generated_dir: Path,
    android_assets_dir: Path | None,
    spellcheck_engine: str,
) -> None:
    topic_map: dict[str, list[dict[str, object]]] = {}
    for job in jobs:
        print(f"처리 중: {job.topic} / {job.source_url}")
        payload = process_single_video(ytt_api, job, generated_dir / "topics", spellcheck_engine)
        topic_map.setdefault(job.topic, []).append(payload)

    topic_payloads = [
        {
            "name": topic,
            "videos": videos,
        }
        for topic, videos in topic_map.items()
    ]
    write_combined_outputs(generated_dir / "app_assets", topic_payloads, android_assets_dir)
    print(f"과목 수: {len(topic_payloads)}")
    print(f"영상 수: {sum(len(topic['videos']) for topic in topic_payloads)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="유튜브 자막을 추출하고 맞춤법 검사 후 오프라인 챗봇 앱용 데이터를 생성합니다."
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help="단일 실행용 유튜브 URL 또는 비디오 ID",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_FILE),
        help="과목별 URL 목록 JSON 파일 경로",
    )
    parser.add_argument(
        "--generated-dir",
        default=str(DEFAULT_GENERATED_DIR),
        help="생성 결과를 저장할 폴더 경로",
    )
    parser.add_argument(
        "--android-assets-dir",
        default=str(DEFAULT_ANDROID_ASSETS_DIR),
        help="Android 앱 assets 폴더 경로",
    )
    parser.add_argument(
        "--env-file",
        default=str(DEFAULT_ENV_FILE),
        help="Webshare 프록시 정보를 읽을 .env 파일 경로",
    )
    parser.add_argument(
        "--single",
        action="store_true",
        help="config 대신 --url 기준으로 단일 영상만 처리",
    )
    parser.add_argument(
        "--proxy-mode",
        choices=["none", "webshare", "generic"],
        default=None,
        help="프록시 모드 선택 (none/webshare/generic). 기본값은 none (직접 연결)",
    )
    parser.add_argument(
        "--proxy-host",
        default=None,
        help="generic 모드에서 사용할 프록시 IP 또는 호스트",
    )
    parser.add_argument(
        "--proxy-port",
        default=None,
        help="generic 모드에서 사용할 프록시 포트",
    )
    parser.add_argument(
        "--spellcheck-engine",
        choices=["gpt", "hanspell", "auto", "none"],
        default="gpt",
        help="맞춤법 검사 엔진 선택. 기본값은 gpt",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_dotenv(args.env_file)

    if args.proxy_mode:
        os.environ[PROXY_MODE_ENV] = args.proxy_mode
    if args.proxy_host:
        os.environ[PROXY_HOST_ENV] = args.proxy_host
    if args.proxy_port:
        os.environ[PROXY_PORT_ENV] = args.proxy_port

    generated_dir = Path(args.generated_dir)
    android_assets_dir = Path(args.android_assets_dir)
    ytt_api = build_transcript_api()

    if args.single:
        job = VideoJob(topic="default", source_url=args.url, video_id=extract_video_id(args.url))
        payload = process_single_video(ytt_api, job, generated_dir / "single", args.spellcheck_engine)
        write_combined_outputs(
            generated_dir / "app_assets",
            [{"name": "default", "videos": [payload]}],
            android_assets_dir,
        )
        print(f"자막 추출 완료: {payload['videoId']}")
        print(f"저장 폴더: {(generated_dir / 'single').resolve()}")
        return

    jobs = load_video_jobs(Path(args.config))
    if not jobs:
        raise RuntimeError("처리할 유튜브 URL이 없습니다. videos.json 내용을 확인하세요.")

    process_batch(ytt_api, jobs, generated_dir, android_assets_dir, args.spellcheck_engine)


if __name__ == "__main__":
    main()