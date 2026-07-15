package com.family.uktour

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.lifecycleScope
import coil.compose.AsyncImage
import com.family.uktour.data.*
import com.family.uktour.player.PlayState
import com.family.uktour.player.TourPlayer
import com.family.uktour.ui.Journey
import com.family.uktour.ui.UKTourTheme
import kotlin.math.roundToInt

class MainActivity : ComponentActivity() {

    private lateinit var repo: TourRepository
    private lateinit var player: TourPlayer
    private lateinit var progress: ProgressStore

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        repo = TourRepository(this)
        progress = ProgressStore(this)
        player = TourPlayer(this, repo, lifecycleScope) { item ->
            if (!item.isMore) progress.markDone(item.file)
        }
        setContent { UKTourTheme { App(repo, player, progress) } }
    }

    override fun onDestroy() {
        player.release()
        super.onDestroy()
    }
}

/** Persists which tracks were finished, for checkmarks and passport stamps. */
class ProgressStore(context: android.content.Context) {
    private val prefs = context.getSharedPreferences("progress", 0)
    private val _done = mutableStateOf(prefs.getStringSet("done", emptySet())!!.toSet())
    val done: State<Set<String>> get() = _done
    fun markDone(file: String) {
        val s = _done.value + file
        _done.value = s
        prefs.edit().putStringSet("done", s).apply()
    }

    fun sightComplete(sight: Sight): Boolean {
        val files = (sight.kid + sight.adult).map { it.file }
        // A stamp is earned when every track of EITHER version has been heard.
        return sight.kid.all { it.file in _done.value } || sight.adult.all { it.file in _done.value }
    }
}

private sealed class Screen {
    data object Days : Screen()
    data class SightScreen(val id: String) : Screen()
    data class DayPlayer(val day: Int) : Screen()
    data object Passport : Screen()
}

@Composable
private fun App(repo: TourRepository, player: TourPlayer, progress: ProgressStore) {
    var screen by remember { mutableStateOf<Screen>(Screen.Days) }
    var kidMode by rememberSaveable { mutableStateOf(true) }

    when (val s = screen) {
        is Screen.Days -> DaysScreen(
            repo, progress, kidMode,
            onKidMode = { kidMode = it },
            onOpenSight = { screen = Screen.SightScreen(it) },
            onPlayDay = { screen = Screen.DayPlayer(it) },
            onOpenPassport = { screen = Screen.Passport }
        )
        is Screen.DayPlayer -> {
            BackHandler { screen = Screen.Days }
            DayPlayerScreen(
                s.day, repo, player, kidMode,
                onKidMode = { kidMode = it },
                onBack = { screen = Screen.Days }
            )
        }
        is Screen.SightScreen -> {
            BackHandler { screen = Screen.Days }
            SightPlayerScreen(
                repo.sight(s.id), repo, player, progress, kidMode,
                onKidMode = { kidMode = it },
                onBack = { screen = Screen.Days }
            )
        }
        is Screen.Passport -> {
            BackHandler { screen = Screen.Days }
            PassportScreen(repo, progress, onBack = { screen = Screen.Days })
        }
    }
}

// ---------------------------------------------------------------- Days list

@Composable
private fun DaysScreen(
    repo: TourRepository,
    progress: ProgressStore,
    kidMode: Boolean,
    onKidMode: (Boolean) -> Unit,
    onOpenSight: (String) -> Unit,
    onPlayDay: (Int) -> Unit,
    onOpenPassport: () -> Unit
) {
    val done by progress.done
    Scaffold(
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = onOpenPassport,
                containerColor = Journey.stampGold,
                contentColor = Journey.ink
            ) {
                Text("🛂  Passport", fontWeight = FontWeight.Bold)
            }
        }
    ) { pad ->
        LazyColumn(
            modifier = Modifier.padding(pad).fillMaxSize(),
            contentPadding = PaddingValues(bottom = 96.dp)
        ) {
            item {
                Column(Modifier.padding(20.dp, 24.dp, 20.dp, 8.dp)) {
                    Text(
                        "OUR BIG TRIP · JULY 2026",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.6f)
                    )
                    Text("London → Edinburgh → York", style = MaterialTheme.typography.displaySmall)
                    Spacer(Modifier.height(12.dp))
                    KidModeSwitch(kidMode, onKidMode)
                }
            }
            repo.sightsByDay().forEach { (day, sights) ->
                item(key = "day-$day") { DayHeader(day, sights.first().date, onPlayDay = { onPlayDay(day) }) }
                items(sights, key = { it.id }) { sight ->
                    SightCard(sight, repo, kidMode, done, progress.sightComplete(sight)) {
                        onOpenSight(sight.id)
                    }
                }
            }
        }
    }
}

@Composable
private fun KidModeSwitch(kidMode: Boolean, onChange: (Boolean) -> Unit) {
    Row(
        Modifier
            .clip(RoundedCornerShape(24.dp))
            .background(MaterialTheme.colorScheme.onBackground.copy(alpha = 0.06f))
            .padding(4.dp)
    ) {
        listOf(true to "🧒 Kids", false to "🧑 Grown-ups").forEach { (mode, label) ->
            val selected = kidMode == mode
            Text(
                label,
                modifier = Modifier
                    .clip(RoundedCornerShape(20.dp))
                    .background(if (selected) MaterialTheme.colorScheme.primary else Color.Transparent)
                    .clickable { onChange(mode) }
                    .padding(horizontal = 16.dp, vertical = 8.dp),
                color = if (selected) Color.White else MaterialTheme.colorScheme.onBackground,
                fontWeight = FontWeight.SemiBold
            )
        }
    }
}

@Composable
private fun DayHeader(day: Int, date: String, onPlayDay: () -> Unit) {
    val accent = Journey.accentForDay(day)
    Row(
        Modifier.padding(20.dp, 20.dp, 20.dp, 6.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Box(
            Modifier.size(10.dp).clip(CircleShape).background(accent)
        )
        Spacer(Modifier.width(10.dp))
        Text(
            "DAY $day · ${date.uppercase()} · ${Journey.cityForDay(day).uppercase()}",
            style = MaterialTheme.typography.labelSmall,
            color = accent
        )
        Spacer(Modifier.weight(1f))
        Row(
            Modifier
                .clip(RoundedCornerShape(16.dp))
                .background(accent.copy(alpha = 0.15f))
                .clickable(onClick = onPlayDay)
                .padding(horizontal = 12.dp, vertical = 5.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(Icons.Filled.PlayArrow, "Play day", tint = accent, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(4.dp))
            Text("Play day", style = MaterialTheme.typography.labelMedium,
                color = accent, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun SightCard(
    sight: Sight,
    repo: TourRepository,
    kidMode: Boolean,
    done: Set<String>,
    stamped: Boolean,
    onClick: () -> Unit
) {
    val art = repo.art[sight.id]
    val accent = Journey.accentForDay(sight.day)
    val tracks = sight.tracks(kidMode)
    val heard = tracks.count { it.file in done }
    val minutes = tracks.sumOf { it.estMinutes } + tracks.sumOf { it.moreMinutes }

    ElevatedCard(
        modifier = Modifier
            .padding(horizontal = 16.dp, vertical = 6.dp)
            .fillMaxWidth()
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(18.dp)
    ) {
        Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            SightThumb(sight, repo, size = 64.dp)
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f)) {
                Text(sight.name, style = MaterialTheme.typography.titleMedium)
                Text(
                    sight.note,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
                    maxLines = 1
                )
                Spacer(Modifier.height(6.dp))
                Text(
                    "${tracks.size} stories · up to ${minutes.roundToInt()} min" +
                        if (heard > 0) " · $heard heard" else "",
                    style = MaterialTheme.typography.labelSmall,
                    color = accent
                )
            }
            if (stamped) StampBadge(small = true)
        }
    }
}

@Composable
private fun SightThumb(sight: Sight, repo: TourRepository, size: androidx.compose.ui.unit.Dp) {
    val art = repo.art[sight.id]
    val imageUrl = remember(sight.id) { repo.localImageAsset(sight.id, 0) }
    Box(
        Modifier
            .size(size)
            .clip(RoundedCornerShape(14.dp))
            .background(Color(art?.color ?: 0xFF888888L)),
        contentAlignment = Alignment.Center
    ) {
        if (imageUrl != null) {
            AsyncImage(
                model = imageUrl,
                contentDescription = sight.name,
                modifier = Modifier.fillMaxSize(),
                contentScale = ContentScale.Crop
            )
        } else {
            Text(art?.emoji ?: "📍", fontSize = (size.value * 0.5f).sp)
        }
    }
}

@Composable
private fun StampBadge(small: Boolean = false) {
    val size = if (small) 40.dp else 84.dp
    Box(
        Modifier
            .size(size)
            .rotate(-12f)
            .clip(CircleShape)
            .background(Journey.stampGold.copy(alpha = 0.15f))
            .padding(3.dp)
            .clip(CircleShape)
            .background(Color.Transparent),
        contentAlignment = Alignment.Center
    ) {
        Text(if (small) "✔" else "VISITED ✔", color = Journey.stampGold,
            fontWeight = FontWeight.Black, fontSize = if (small) 18.sp else 13.sp,
            textAlign = TextAlign.Center)
    }
}

// ---------------------------------------------------------- Sight + player

@Composable
private fun SightPlayerScreen(
    sight: Sight,
    repo: TourRepository,
    player: TourPlayer,
    progress: ProgressStore,
    kidMode: Boolean,
    onKidMode: (Boolean) -> Unit,
    onBack: () -> Unit
) {
    val ui by player.ui.collectAsStateWithLifecycle()
    val done by progress.done
    val tracks = sight.tracks(kidMode)
    val art = repo.art[sight.id]
    val accent = Journey.accentForDay(sight.day)

    // Which base track is current (for highlighting and Tell-me-more).
    val currentBase = ui.current?.baseIndex ?: -1
    val currentTrack = tracks.getOrNull(currentBase)

    // Hero image for the currently playing story (bundled offline assets;
    // falls back to the sight's first image, then to the emoji placeholder).
    val heroUrl = remember(sight.id, currentBase) {
        val idx = if (currentBase >= 0) currentBase else 0
        repo.localImageAsset(sight.id, idx) ?: repo.localImageAsset(sight.id, 0)
    }

    Scaffold(
        topBar = {
            Row(
                Modifier.fillMaxWidth().padding(8.dp, 12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(onClick = onBack) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back")
                }
                Column(Modifier.weight(1f)) {
                    Text(sight.name, style = MaterialTheme.typography.headlineSmall, maxLines = 1)
                    Text(
                        "Day ${sight.day} · ${sight.date}",
                        style = MaterialTheme.typography.labelSmall, color = accent
                    )
                }
                KidModeSwitch(kidMode, onKidMode)
            }
        },
        bottomBar = {
            PlayerBar(
                ui = ui,
                accent = accent,
                canTellMore = currentTrack?.hasMore == true &&
                    ui.current?.isMore != true,
                kidMode = kidMode,
                onPlayPause = { if (ui.position < 0) player.load(tracks) else player.playPause() },
                onNext = player::next,
                onPrev = player::previous,
                onTellMore = { currentTrack?.let(player::tellMeMore) },
                onRate = player::setSpeechRate,
                onSeek = player::seekTo,
                onCancelGap = player::cancelGap
            )
        }
    ) { pad ->
        LazyColumn(Modifier.padding(pad).fillMaxSize()) {
            item {
                Box(
                    Modifier
                        .padding(16.dp)
                        .fillMaxWidth()
                        .height(if (kidMode) 220.dp else 170.dp)
                        .clip(RoundedCornerShape(22.dp))
                        .background(Color(art?.color ?: 0xFF888888L)),
                    contentAlignment = Alignment.Center
                ) {
                    if (heroUrl != null) {
                        AsyncImage(
                            model = heroUrl, contentDescription = null,
                            modifier = Modifier.fillMaxSize(), contentScale = ContentScale.Crop
                        )
                    } else {
                        Text(art?.emoji ?: "📍", fontSize = 72.sp)
                    }
                    if (kidMode && art != null) {
                        Text(
                            art.emoji, fontSize = 40.sp,
                            modifier = Modifier.align(Alignment.TopEnd).padding(12.dp)
                        )
                    }
                }
            }
            item {
                if (ui.current != null) {
                    Text(
                        text = (if (ui.current!!.isMore) "✨ " else "") + ui.current!!.title,
                        style = MaterialTheme.typography.headlineSmall,
                        modifier = Modifier.padding(horizontal = 20.dp),
                        color = if (ui.current!!.isMore) accent else MaterialTheme.colorScheme.onBackground
                    )
                    Spacer(Modifier.height(8.dp))
                }
            }
            items(tracks.size) { i ->
                val t = tracks[i]
                val isCurrent = i == currentBase
                TrackRow(
                    index = i + 1,
                    track = t,
                    accent = accent,
                    playing = isCurrent && ui.state == PlayState.PLAYING,
                    current = isCurrent,
                    heard = t.file in done,
                    kidMode = kidMode
                ) { player.load(tracks, i) }
            }
            item { Spacer(Modifier.height(24.dp)) }
        }
    }
}

@Composable
private fun TrackRow(
    index: Int,
    track: Track,
    accent: Color,
    playing: Boolean,
    current: Boolean,
    heard: Boolean,
    kidMode: Boolean,
    onClick: () -> Unit
) {
    Row(
        Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .background(if (current) accent.copy(alpha = 0.08f) else Color.Transparent)
            .padding(horizontal = 20.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Box(
            Modifier.size(34.dp).clip(CircleShape)
                .background(if (current) accent else accent.copy(alpha = 0.12f)),
            contentAlignment = Alignment.Center
        ) {
            when {
                playing -> Icon(Icons.Filled.GraphicEq, null, tint = Color.White, modifier = Modifier.size(18.dp))
                current -> Icon(Icons.Filled.Pause, null, tint = Color.White, modifier = Modifier.size(18.dp))
                else -> Text("$index", color = accent, fontWeight = FontWeight.Bold)
            }
        }
        Spacer(Modifier.width(14.dp))
        Column(Modifier.weight(1f)) {
            Text(
                track.title,
                style = MaterialTheme.typography.titleMedium,
                fontFamily = if (kidMode) FontFamily.Default else FontFamily.Serif
            )
            Text(
                "≈ ${track.estMinutes.roundToInt().coerceAtLeast(1)} min" +
                    (if (track.hasMore) " · +${track.moreMinutes.roundToInt().coerceAtLeast(1)} min more" else ""),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.55f)
            )
        }
        if (heard) Text("✔", color = Journey.stampGold, fontWeight = FontWeight.Black)
    }
}

@Composable
private fun DayPlayerScreen(
    day: Int,
    repo: TourRepository,
    player: TourPlayer,
    kidMode: Boolean,
    onKidMode: (Boolean) -> Unit,
    onBack: () -> Unit
) {
    val ui by player.ui.collectAsStateWithLifecycle()
    val accent = Journey.accentForDay(day)
    val sights = remember(day) { repo.sightsByDay().firstOrNull { it.first == day }?.second ?: emptyList() }

    // Whole-day queue: base stories only, sight after sight. Deep dives are
    // opt-in via Tell me more — pre-expanding them made a day hours long.
    val rows = remember(day, kidMode) {
        sights.flatMap { sight ->
            sight.tracks(kidMode).mapIndexed { i, t ->
                com.family.uktour.player.QueueItem(t.file, t.title, false, i, sight.name)
            }
        }
    }
    val moreMinByFile = remember(day) {
        sights.flatMap { it.kid + it.adult }.associate { it.file to it.moreMinutes }
    }
    LaunchedEffect(day, kidMode) { player.loadQueue(rows) }

    // Resolve the playing story across BOTH audiences, so Tell me more works
    // even if the mode was toggled after the queue was built.
    val playingTrack = remember(ui.current?.file, day) {
        sights.asSequence().flatMap { (it.kid + it.adult).asSequence() }
            .firstOrNull { t -> t.file == ui.current?.file }
    }
    // After a Tell-me-more insertion the live queue is longer than rows: show it.
    val shown = if (ui.queue.isNotEmpty() && rows.any { r -> r.file == ui.queue.first().file }) ui.queue else rows

    Scaffold(
        topBar = {
            Row(
                Modifier.fillMaxWidth().padding(8.dp, 12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") }
                Column(Modifier.weight(1f)) {
                    Text("Play the whole day", style = MaterialTheme.typography.headlineSmall, maxLines = 1)
                    Text("Day $day · ${Journey.cityForDay(day)} · ${shown.size} stories",
                        style = MaterialTheme.typography.labelSmall, color = accent)
                }
                KidModeSwitch(kidMode, onKidMode)
            }
        },
        bottomBar = {
            PlayerBar(
                ui = ui, accent = accent,
                canTellMore = playingTrack?.hasMore == true && ui.current?.isMore != true,
                kidMode = kidMode,
                onPlayPause = { if (ui.position < 0) player.loadQueue(rows) else player.playPause() },
                onNext = player::next, onPrev = player::previous,
                onTellMore = { playingTrack?.let(player::tellMeMore) },
                onRate = player::setSpeechRate, onSeek = player::seekTo,
                onCancelGap = player::cancelGap
            )
        }
    ) { pad ->
        LazyColumn(Modifier.padding(pad).fillMaxSize(), contentPadding = PaddingValues(bottom = 16.dp)) {
            itemsIndexed(shown) { i, item ->
                val playing = ui.position == i
                val extraMin = if (!item.isMore) (moreMinByFile[item.file] ?: 0.0) else 0.0
                Row(
                    Modifier.fillMaxWidth()
                        .background(if (playing) accent.copy(alpha = 0.12f) else Color.Transparent)
                        .clickable { player.skipTo(i) }
                        .padding(horizontal = 18.dp, vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(if (playing) "▶" else if (item.isMore) "  ·" else "${i + 1}",
                        modifier = Modifier.width(28.dp), color = accent,
                        fontWeight = FontWeight.Bold)
                    Spacer(Modifier.width(8.dp))
                    Column(Modifier.weight(1f)) {
                        Text(item.title,
                            style = MaterialTheme.typography.bodyLarge,
                            fontFamily = if (kidMode) FontFamily.Default else FontFamily.Serif,
                            fontWeight = if (item.isMore) FontWeight.Normal else FontWeight.SemiBold)
                        Text((if (item.isMore) "deep dive · " else "") + item.sight +
                            (if (extraMin >= 1) " · +${extraMin.roundToInt()} min extras" else ""),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.55f))
                    }
                }
            }
        }
    }
}

@Composable
private fun PlayerBar(
    ui: com.family.uktour.player.PlayerUi,
    accent: Color,
    canTellMore: Boolean,
    kidMode: Boolean,
    onPlayPause: () -> Unit,
    onNext: () -> Unit,
    onPrev: () -> Unit,
    onTellMore: () -> Unit,
    onRate: (Float) -> Unit,
    onSeek: (Float) -> Unit,
    onCancelGap: () -> Unit = {}
) {
    Surface(shadowElevation = 12.dp) {
        Column(Modifier.fillMaxWidth().padding(bottom = 12.dp)) {
            // Draggable scrubber — drag across to skip forward/back within the story.
            var dragging by remember { mutableStateOf(false) }
            var dragValue by remember { mutableFloatStateOf(0f) }
            Slider(
                value = if (dragging) dragValue else ui.progress.coerceIn(0f, 1f),
                onValueChange = { dragging = true; dragValue = it },
                onValueChangeFinished = { onSeek(dragValue); dragging = false },
                enabled = ui.position >= 0,
                colors = SliderDefaults.colors(
                    thumbColor = accent, activeTrackColor = accent,
                    inactiveTrackColor = accent.copy(alpha = 0.25f)
                ),
                modifier = Modifier.fillMaxWidth().padding(horizontal = 10.dp)
            )
            if (ui.state == PlayState.GAP && ui.next != null) {
                // Visible, skippable walking gap: ▶ = next story now, ✕ = stay here.
                Row(
                    Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 20.dp, vertical = 4.dp)
                        .clip(RoundedCornerShape(14.dp))
                        .background(MaterialTheme.colorScheme.onBackground.copy(alpha = 0.06f))
                        .padding(start = 14.dp, end = 4.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        "Next: ${ui.next!!.title} in ${ui.gapRemaining}s",
                        modifier = Modifier.weight(1f),
                        style = MaterialTheme.typography.bodyMedium,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    TextButton(onClick = onCancelGap) { Text("✕ stay") }
                }
            }
            if (canTellMore) {
                Button(
                    onClick = onTellMore,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 20.dp, vertical = 8.dp)
                        .height(if (kidMode) 52.dp else 44.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Journey.stampGold, contentColor = Journey.ink),
                    shape = RoundedCornerShape(26.dp)
                ) {
                    Text(
                        if (kidMode) "✨ Tell me MORE!" else "Tell me more",
                        fontWeight = FontWeight.Bold,
                        fontSize = if (kidMode) 17.sp else 15.sp
                    )
                }
            } else Spacer(Modifier.height(8.dp))
            Row(
                Modifier.fillMaxWidth().padding(horizontal = 12.dp),
                horizontalArrangement = Arrangement.SpaceEvenly,
                verticalAlignment = Alignment.CenterVertically
            ) {
                SpeedButton(ui.speechRate, onRate)
                IconButton(onClick = onPrev, modifier = Modifier.size(52.dp)) {
                    Icon(Icons.Filled.SkipPrevious, "Previous", modifier = Modifier.size(34.dp))
                }
                FilledIconButton(
                    onClick = onPlayPause,
                    modifier = Modifier.size(68.dp),
                    colors = IconButtonDefaults.filledIconButtonColors(containerColor = accent)
                ) {
                    Icon(
                        if (ui.state == PlayState.PLAYING) Icons.Filled.Pause else Icons.Filled.PlayArrow,
                        if (ui.state == PlayState.PLAYING) "Pause" else "Play",
                        modifier = Modifier.size(38.dp), tint = Color.White
                    )
                }
                IconButton(onClick = onNext, modifier = Modifier.size(52.dp)) {
                    Icon(Icons.Filled.SkipNext, "Next", modifier = Modifier.size(34.dp))
                }
                Text(
                    if (ui.usingRecordedAudio) "🎙" else "🤖",
                    fontSize = 18.sp,
                    modifier = Modifier.width(40.dp),
                    textAlign = TextAlign.Center
                )
            }
        }
    }
}

@Composable
private fun SpeedButton(rate: Float, onRate: (Float) -> Unit) {
    val speeds = listOf(0.8f, 1.0f, 1.2f, 1.5f)
    TextButton(onClick = {
        val next = speeds[(speeds.indexOfFirst { it >= rate - 0.01f } + 1) % speeds.size]
        onRate(next)
    }, modifier = Modifier.width(56.dp)) {
        Text("${if (rate % 1f == 0f) rate.toInt().toString() else rate}×", fontWeight = FontWeight.Bold)
    }
}

// -------------------------------------------------------------- Passport

@Composable
private fun PassportScreen(repo: TourRepository, progress: ProgressStore, onBack: () -> Unit) {
    Scaffold(topBar = {
        Row(Modifier.padding(8.dp, 12.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") }
            Text("Tour Passport", style = MaterialTheme.typography.headlineSmall)
        }
    }) { pad ->
        val stamped = repo.sights.count { progress.sightComplete(it) }
        LazyColumn(Modifier.padding(pad), contentPadding = PaddingValues(16.dp)) {
            item {
                Text(
                    "$stamped of ${repo.sights.size} places stamped",
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.padding(bottom = 12.dp)
                )
            }
            items(repo.sights, key = { it.id }) { sight ->
                val complete = progress.sightComplete(sight)
                val art = repo.art[sight.id]
                Row(
                    Modifier.fillMaxWidth().padding(vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(art?.emoji ?: "📍", fontSize = 30.sp, modifier = Modifier.width(48.dp))
                    Column(Modifier.weight(1f)) {
                        Text(sight.name, style = MaterialTheme.typography.titleMedium,
                            color = if (complete) MaterialTheme.colorScheme.onBackground
                            else MaterialTheme.colorScheme.onBackground.copy(alpha = 0.4f))
                        Text("Day ${sight.day}", style = MaterialTheme.typography.labelSmall,
                            color = Journey.accentForDay(sight.day))
                    }
                    if (complete) StampBadge() else Text(
                        "not yet", style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.3f)
                    )
                }
            }
        }
    }
}
