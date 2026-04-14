package com.example.mathchatbot

import android.os.Bundle
import android.view.inputmethod.EditorInfo
import android.view.inputmethod.InputMethodManager
import android.widget.EditText
import android.widget.ImageButton
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.chip.Chip
import com.google.android.material.chip.ChipGroup
import org.json.JSONArray
import org.json.JSONObject
import kotlin.math.roundToInt

class MainActivity : AppCompatActivity() {

    data class Snippet(
        val text: String,
        val start: Double,
        val duration: Double,
    )

    data class VideoEntry(
        val topic: String,
        val displayTitle: String,
        val sourceUrl: String,
        val videoId: String,
        val searchText: String,
        val snippets: List<Snippet>,
    )

    data class TopicEntry(
        val name: String,
        val videos: List<VideoEntry>,
    )

    data class SearchMatch(
        val topic: String,
        val sourceUrl: String,
        val snippet: Snippet,
        val score: Int,
    )

    private lateinit var recyclerView: RecyclerView
    private lateinit var editText: EditText
    private lateinit var sendButton: ImageButton
    private lateinit var subjectChipGroup: ChipGroup
    private lateinit var chatAdapter: ChatAdapter

    private val messages = mutableListOf<ChatMessage>()
    private val topics = mutableListOf<TopicEntry>()
    private var selectedTopic: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        findViewById<TextView>(R.id.titleText).text = getString(R.string.app_name)
        recyclerView = findViewById(R.id.recyclerView)
        editText = findViewById(R.id.editText)
        sendButton = findViewById(R.id.sendButton)
        subjectChipGroup = findViewById(R.id.subjectChipGroup)

        chatAdapter = ChatAdapter(messages)
        val layoutManager = LinearLayoutManager(this)
        layoutManager.stackFromEnd = true
        recyclerView.layoutManager = layoutManager
        recyclerView.adapter = chatAdapter

        topics.addAll(loadTopics())
        renderTopicChips()
        addBotMessage(buildIntroMessage())

        sendButton.setOnClickListener { sendMessage() }
        editText.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_SEND) {
                sendMessage()
                true
            } else {
                false
            }
        }
    }

    private fun loadTopics(): List<TopicEntry> {
        return try {
            val root = JSONObject(assets.open("math_topics.json").bufferedReader().use { it.readText() })
            val topicArray = root.optJSONArray("topics") ?: JSONArray()
            buildList {
                for (index in 0 until topicArray.length()) {
                    val topicObject = topicArray.getJSONObject(index)
                    val videosArray = topicObject.optJSONArray("videos") ?: JSONArray()
                    val videos = buildList {
                        for (videoIndex in 0 until videosArray.length()) {
                            val videoObject = videosArray.getJSONObject(videoIndex)
                            val snippetsArray = videoObject.optJSONArray("snippets") ?: JSONArray()
                            val snippets = buildList {
                                for (snippetIndex in 0 until snippetsArray.length()) {
                                    val snippetObject = snippetsArray.getJSONObject(snippetIndex)
                                    add(
                                        Snippet(
                                            text = snippetObject.optString("text"),
                                            start = snippetObject.optDouble("start"),
                                            duration = snippetObject.optDouble("duration"),
                                        )
                                    )
                                }
                            }

                            add(
                                VideoEntry(
                                    topic = videoObject.optString("topic"),
                                    displayTitle = videoObject.optString("displayTitle"),
                                    sourceUrl = videoObject.optString("sourceUrl"),
                                    videoId = videoObject.optString("videoId"),
                                    searchText = videoObject.optString("searchText"),
                                    snippets = snippets,
                                )
                            )
                        }
                    }

                    add(TopicEntry(topicObject.optString("name"), videos))
                }
            }
        } catch (_: Exception) {
            emptyList()
        }
    }

    private fun renderTopicChips() {
        subjectChipGroup.removeAllViews()
        addTopicChip("전체", null, true)
        topics.forEach { topic ->
            addTopicChip(topic.name, topic.name, false)
        }
    }

    private fun addTopicChip(label: String, topicName: String?, isChecked: Boolean) {
        val chip = layoutInflater.inflate(R.layout.item_topic_chip, subjectChipGroup, false) as Chip
        chip.text = label
        chip.isChecked = isChecked
        chip.setOnClickListener {
            selectedTopic = topicName
            addBotMessage(
                if (topicName == null) {
                    "전체 과목 검색으로 전환했습니다. 질문을 입력하면 모든 자막에서 찾아봅니다."
                } else {
                    "$topicName 과목으로 범위를 좁혔습니다. 해당 과목 중심으로 질문해 보세요."
                }
            )
            refreshScroll()
        }
        subjectChipGroup.addView(chip)
    }

    private fun buildIntroMessage(): String {
        val topicNames = if (topics.isEmpty()) {
            "아직 자막 데이터가 없습니다. Python 파이프라인을 먼저 실행하세요."
        } else {
            topics.joinToString(separator = ", ") { it.name }
        }

        return "안녕하세요. 수학 자막 오프라인 챗봇입니다.\n\n" +
            "현재 과목: $topicNames\n\n" +
            "사용 방법\n" +
            "1. 위에서 과목을 선택합니다.\n" +
            "2. 질문을 입력합니다.\n" +
            "3. 앱이 로컬 자막에서 관련 구간을 찾아 답변합니다."
    }

    private fun sendMessage() {
        val query = editText.text.toString().trim()
        if (query.isEmpty()) return

        addUserMessage(query)
        editText.setText("")

        val imm = getSystemService(INPUT_METHOD_SERVICE) as InputMethodManager
        imm.hideSoftInputFromWindow(editText.windowToken, 0)

        addBotMessage(searchInTopics(query))
    }

    private fun searchInTopics(query: String): String {
        val normalizedTokens = tokenize(query)
        if (normalizedTokens.isEmpty()) {
            return "검색어가 너무 짧습니다. 두 글자 이상으로 질문해 주세요."
        }

        val candidateVideos = topics
            .filter { selectedTopic == null || it.name == selectedTopic }
            .flatMap { it.videos }

        if (candidateVideos.isEmpty()) {
            return "앱 자산에 자막 데이터가 아직 없습니다. Python 파이프라인을 먼저 실행해 주세요."
        }

        val matches = mutableListOf<SearchMatch>()
        candidateVideos.forEach { video ->
            val normalizedSearchText = normalize(video.searchText)
            video.snippets.forEach { snippet ->
                val normalizedSnippet = normalize(snippet.text)
                var score = 0

                normalizedTokens.forEach { token ->
                    if (normalizedSearchText.contains(token)) {
                        score += 2
                    }
                    if (normalizedSnippet.contains(token)) {
                        score += 5
                    }
                    if (normalize(video.topic).contains(token)) {
                        score += 3
                    }
                }

                if (score > 0) {
                    matches.add(
                        SearchMatch(
                            topic = video.topic,
                            sourceUrl = video.sourceUrl,
                            snippet = snippet,
                            score = score,
                        )
                    )
                }
            }
        }

        if (matches.isEmpty()) {
            val topicHint = selectedTopic ?: "전체 과목"
            return "$topicHint 범위에서 관련 자막을 찾지 못했습니다. 다른 키워드로 질문해 보세요."
        }

        val topMatches = matches
            .sortedWith(compareByDescending<SearchMatch> { it.score }.thenBy { it.snippet.start })
            .take(3)

        return buildString {
            append("질문: ")
            append(query)
            append("\n\n관련 자막 구간\n")
            topMatches.forEachIndexed { index, match ->
                append(index + 1)
                append(". [")
                append(match.topic)
                append("] ")
                append(formatTimestamp(match.snippet.start))
                append("\n")
                append(match.snippet.text)
                append("\n링크: ")
                append(buildTimestampUrl(match.sourceUrl, match.snippet.start))
                append("\n\n")
            }
        }.trim()
    }

    private fun buildTimestampUrl(sourceUrl: String, startSeconds: Double): String {
        val seconds = startSeconds.toInt()
        val cleaned = sourceUrl
            .replace(Regex("""&t=[^&#]*"""), "")
            .replace(Regex("""\?t=[^&#]*&"""), "?")
            .replace(Regex("""\?t=[^&#]*$"""), "")
        val connector = if (cleaned.contains("?")) "&" else "?"
        return "${cleaned}${connector}t=${seconds}s"
    }

    private fun tokenize(query: String): List<String> {
        val collapsed = query.trim()
        if (collapsed.isEmpty()) return emptyList()

        val tokens = linkedSetOf<String>()
        val merged = normalize(collapsed)
        if (merged.length >= 2) {
            tokens.add(merged)
        }

        collapsed.split(Regex("\\s+"))
            .map { normalize(it) }
            .filter { it.length >= 2 }
            .forEach(tokens::add)

        return tokens.toList()
    }

    private fun normalize(value: String): String {
        return value.lowercase().replace(Regex("[^\\p{L}\\p{N}]+"), "")
    }

    private fun formatTimestamp(seconds: Double): String {
        val total = seconds.roundToInt()
        val minutes = total / 60
        val remainingSeconds = total % 60
        return "%02d:%02d".format(minutes, remainingSeconds)
    }

    private fun addUserMessage(text: String) {
        messages.add(ChatMessage(text, true))
        chatAdapter.notifyItemInserted(messages.lastIndex)
        refreshScroll()
    }

    private fun addBotMessage(text: String) {
        messages.add(ChatMessage(text, false))
        chatAdapter.notifyItemInserted(messages.lastIndex)
        refreshScroll()
    }

    private fun refreshScroll() {
        recyclerView.post {
            recyclerView.scrollToPosition(messages.lastIndex)
        }
    }
}