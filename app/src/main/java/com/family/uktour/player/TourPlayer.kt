package com.family.uktour.player

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.media.MediaPlayer
import android.os.Bundle
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import com.family.uktour.data.Track
import com.family.uktour.data.TourRepository
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import java.util.Locale

enum class PlayState { IDLE, PLAYING, PAUSED, GAP }

/** One item in the play queue: a base track or a queued "Tell me more". */
data class QueueItem(
    val file: String,
    val title: String,
    val isMore: Boolean,
    val baseIndex: Int,
    val sight: String = ""
)

data class PlayerUi(
    val state: PlayState = PlayState.IDLE,
    val queue: List<QueueItem> = emptyList(),
    val position: Int = -1,
    val progress: Float = 0f,          // 0..1 within the current item
    val usingRecordedAudio: Boolean = false,
    val speechRate: Float = 1.0f,
    val gapRemaining: Int = 0          // seconds left in the walking gap (state == GAP)
) {
    val current: QueueItem? get() = queue.getOrNull(position)
    val next: QueueItem? get() = queue.getOrNull(position + 1)
}

/**
 * Plays a sight's tracks. If pre-rendered audio exists in assets it uses
 * MediaPlayer (natural voices, real seek); otherwise it speaks the markdown
 * with Android TextToSpeech, chunked into sentences so pause/resume work.
 */
class TourPlayer(
    private val context: Context,
    private val repo: TourRepository,
    private val scope: CoroutineScope,
    private val onTrackFinished: (QueueItem) -> Unit
) {
    private val _ui = MutableStateFlow(PlayerUi())
    val ui: StateFlow<PlayerUi> = _ui

    private var tts: TextToSpeech? = null
    private var ttsReady = false
    private var media: MediaPlayer? = null
    private var sentences: List<String> = emptyList()
    private var sentenceIndex = 0
    private var progressJob: Job? = null
    private var gapJob: Job? = null
    private val gapMs = 30_000L   // silence gap at the end of each track before auto-advance

    private val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    private var focusRequest: AudioFocusRequest? = null
    private var pausedByFocusLoss = false

    init {
        tts = TextToSpeech(context) { status ->
            if (status == TextToSpeech.SUCCESS) {
                tts?.language = Locale.UK
                ttsReady = true
            }
        }
        tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(id: String?) {}
            override fun onError(id: String?) {}
            override fun onDone(id: String?) {
                scope.launch { advanceSentence() }
            }
        })
    }

    fun load(tracks: List<Track>, startIndex: Int = 0) {
        stopEngines()
        val queue = tracks.mapIndexed { i, t -> QueueItem(t.file, t.title, false, i) }
        _ui.value = PlayerUi(queue = queue, position = startIndex, speechRate = _ui.value.speechRate)
        playCurrent()
    }

    /** Load a fully pre-expanded queue (e.g. a whole day: each story's base track
     *  followed inline by its deep-dive chapters). No on-demand insertion. */
    fun loadQueue(items: List<QueueItem>, startIndex: Int = 0) {
        stopEngines()
        _ui.value = PlayerUi(queue = items, position = startIndex, speechRate = _ui.value.speechRate)
        playCurrent()
    }

    /** Insert the current track's Tell Me More chapters right after it and jump to the first. */
    fun tellMeMore(track: Track) {
        if (track.more.isEmpty()) return
        val ui = _ui.value
        val pos = ui.position
        // Already queued? (first chapter sits right after the current item) — just jump.
        if (ui.queue.getOrNull(pos + 1)?.file == track.more.first().file) { skipTo(pos + 1); return }
        val baseIndex = ui.queue[pos].baseIndex
        val items = track.more.map { QueueItem(it.file, it.title, true, baseIndex, ui.queue[pos].sight) }
        val newQueue = ui.queue.toMutableList().apply { addAll(pos + 1, items) }
        _ui.value = ui.copy(queue = newQueue)
        skipTo(pos + 1)
    }

    fun playPause() {
        when (_ui.value.state) {
            PlayState.PLAYING -> pause()
            PlayState.PAUSED -> resume()
            // During the walking gap, the play button means "next story now".
            PlayState.GAP -> skipTo(_ui.value.position + 1)
            PlayState.IDLE -> if (_ui.value.position >= 0) playCurrent()
        }
    }

    /** "Stay here": cancel the pending auto-advance and go quiet. */
    fun cancelGap() {
        if (_ui.value.state != PlayState.GAP) return
        gapJob?.cancel()
        _ui.value = _ui.value.copy(state = PlayState.IDLE, gapRemaining = 0)
    }

    fun skipTo(index: Int) {
        if (index !in _ui.value.queue.indices) return
        stopEngines()
        _ui.value = _ui.value.copy(position = index, progress = 0f)
        playCurrent()
    }

    fun next() {
        val ui = _ui.value
        if (ui.position + 1 < ui.queue.size) skipTo(ui.position + 1)
        else { stopEngines(); _ui.value = ui.copy(state = PlayState.IDLE, progress = 1f) }
    }

    fun previous() {
        val ui = _ui.value
        if (ui.progress > 0.15f) skipTo(ui.position)     // restart current first
        else if (ui.position > 0) skipTo(ui.position - 1)
        else skipTo(0)
    }

    /** Scrub within the current track. Fraction 0..1. Recorded audio seeks the
     *  MediaPlayer; spoken (TTS) fallback jumps to the nearest sentence. */
    fun seekTo(fraction: Float) {
        val f = fraction.coerceIn(0f, 1f)
        if (_ui.value.usingRecordedAudio) {
            media?.let { m ->
                val d = runCatching { m.duration }.getOrDefault(0)
                if (d > 0) {
                    runCatching { m.seekTo((f * d).toInt()) }
                    _ui.value = _ui.value.copy(progress = f)
                }
            }
        } else if (sentences.isNotEmpty()) {
            sentenceIndex = (f * sentences.size).toInt().coerceIn(0, sentences.lastIndex)
            _ui.value = _ui.value.copy(progress = sentenceIndex.toFloat() / sentences.size)
            if (_ui.value.state == PlayState.PLAYING) speakSentence()
        }
    }

    fun setSpeechRate(rate: Float) {
        _ui.value = _ui.value.copy(speechRate = rate)
        tts?.setSpeechRate(rate)
        media?.let { m ->
            runCatching { m.playbackParams = m.playbackParams.setSpeed(rate) }
        }
    }

    fun release() {
        stopEngines()
        tts?.shutdown()
        tts = null
    }

    // ---- internals -------------------------------------------------------

    private fun playCurrent() {
        val item = _ui.value.current ?: return
        requestFocus()
        val audio = repo.audioAssetPath(item.file)
        if (audio != null) playRecorded(audio) else speak(item.file)
    }

    private fun playRecorded(assetPath: String) {
        val mp = MediaPlayer()
        media = mp
        val afd = context.assets.openFd(assetPath)
        mp.setDataSource(afd.fileDescriptor, afd.startOffset, afd.length)
        afd.close()
        mp.setAudioAttributes(
            AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                .build()
        )
        mp.setOnPreparedListener {
            runCatching { it.playbackParams = it.playbackParams.setSpeed(_ui.value.speechRate) }
            it.start()
            _ui.value = _ui.value.copy(state = PlayState.PLAYING, usingRecordedAudio = true)
            watchMediaProgress()
        }
        mp.setOnCompletionListener { finishedCurrent() }
        mp.prepareAsync()
    }

    private fun speak(file: String) {
        if (!ttsReady) {
            scope.launch { delay(400); if (ttsReady) speak(file) }
            return
        }
        val text = repo.trackText(file)
        sentences = splitSentences(text)
        sentenceIndex = 0
        _ui.value = _ui.value.copy(state = PlayState.PLAYING, usingRecordedAudio = false, progress = 0f)
        tts?.setSpeechRate(_ui.value.speechRate)
        speakSentence()
    }

    private fun speakSentence() {
        val s = sentences.getOrNull(sentenceIndex) ?: run { finishedCurrent(); return }
        tts?.speak(s, TextToSpeech.QUEUE_FLUSH, Bundle(), "s-$sentenceIndex")
    }

    private fun advanceSentence() {
        if (_ui.value.state != PlayState.PLAYING || _ui.value.usingRecordedAudio) return
        sentenceIndex++
        _ui.value = _ui.value.copy(
            progress = if (sentences.isEmpty()) 1f else sentenceIndex.toFloat() / sentences.size
        )
        if (sentenceIndex >= sentences.size) finishedCurrent() else speakSentence()
    }

    private fun finishedCurrent() {
        _ui.value.current?.let(onTrackFinished)
        progressJob?.cancel()
        media?.release(); media = null
        val ui = _ui.value
        if (ui.position + 1 < ui.queue.size) {
            // Walking gap before the next stop's story; chapters of the same
            // deep dive chain after a beat instead of 30s of dead air.
            val gapSec = if (ui.queue[ui.position + 1].isMore) 1 else (gapMs / 1000L).toInt()
            _ui.value = ui.copy(state = PlayState.GAP, progress = 1f, gapRemaining = gapSec)
            gapJob?.cancel()
            gapJob = scope.launch {
                for (s in gapSec downTo 1) {
                    _ui.value = _ui.value.copy(gapRemaining = s)
                    delay(1000)
                }
                skipTo(_ui.value.position + 1)
            }
        } else {
            _ui.value = ui.copy(state = PlayState.IDLE, progress = 1f, gapRemaining = 0)
            abandonFocus()
        }
    }

    private fun pause() {
        gapJob?.cancel()
        if (_ui.value.usingRecordedAudio) media?.pause() else tts?.stop()
        progressJob?.cancel()
        _ui.value = _ui.value.copy(state = PlayState.PAUSED)
    }

    private fun resume() {
        // The engine may be gone (e.g. the track finished while paused).
        if (_ui.value.usingRecordedAudio && media == null) {
            if (_ui.value.position + 1 < _ui.value.queue.size) skipTo(_ui.value.position + 1)
            else skipTo(_ui.value.position)
            return
        }
        requestFocus()
        _ui.value = _ui.value.copy(state = PlayState.PLAYING)
        if (_ui.value.usingRecordedAudio) { media?.start(); watchMediaProgress() }
        else speakSentence()
    }

    private fun stopEngines() {
        gapJob?.cancel()
        progressJob?.cancel()
        tts?.stop()
        media?.release(); media = null
        _ui.value = _ui.value.copy(state = PlayState.IDLE, gapRemaining = 0)
    }

    private fun watchMediaProgress() {
        progressJob?.cancel()
        progressJob = scope.launch {
            while (true) {
                val m = media ?: break
                val d = runCatching { m.duration }.getOrDefault(0)
                if (d > 0) {
                    val p = runCatching { m.currentPosition }.getOrDefault(0)
                    _ui.value = _ui.value.copy(progress = p.toFloat() / d)
                }
                delay(500)
            }
        }
    }

    private fun requestFocus() {
        if (focusRequest != null) return
        val req = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN)
            .setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .build()
            )
            .setOnAudioFocusChangeListener { change ->
                when (change) {
                    AudioManager.AUDIOFOCUS_LOSS -> {
                        // Another app took over for good: release the (now stale)
                        // request so the next play re-acquires focus properly.
                        pausedByFocusLoss = false
                        if (_ui.value.state == PlayState.PLAYING) pause()
                        abandonFocus()
                    }
                    AudioManager.AUDIOFOCUS_LOSS_TRANSIENT -> {
                        if (_ui.value.state == PlayState.PLAYING) {
                            pause(); pausedByFocusLoss = true
                        }
                    }
                    AudioManager.AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK ->
                        media?.setVolume(0.25f, 0.25f)
                    AudioManager.AUDIOFOCUS_GAIN -> {
                        media?.setVolume(1f, 1f)
                        // Navigation prompt / phone call over: pick the tour back up.
                        if (pausedByFocusLoss) { pausedByFocusLoss = false; resume() }
                    }
                }
            }
            .build()
        if (audioManager.requestAudioFocus(req) == AudioManager.AUDIOFOCUS_REQUEST_GRANTED) {
            focusRequest = req
        }
    }

    private fun abandonFocus() {
        focusRequest?.let { audioManager.abandonAudioFocusRequest(it) }
        focusRequest = null
    }

    companion object {
        fun splitSentences(text: String): List<String> {
            val flat = text.replace('\n', ' ').replace(Regex("\\s+"), " ").trim()
            if (flat.isEmpty()) return emptyList()
            val parts = flat.split(Regex("(?<=[.!?…])\\s+"))
            // Merge very short fragments (abbreviations etc.) into their neighbor.
            val merged = mutableListOf<String>()
            for (p in parts) {
                if (merged.isNotEmpty() && (p.length < 12 || merged.last().length < 12)) {
                    merged[merged.size - 1] = merged.last() + " " + p
                } else merged += p
            }
            return merged
        }
    }
}
