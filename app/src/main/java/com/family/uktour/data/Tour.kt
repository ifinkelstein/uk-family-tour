package com.family.uktour.data

import android.content.Context
import org.json.JSONObject

data class MoreChapter(val file: String, val title: String, val minutes: Double)

data class Track(
    val file: String,
    val title: String,
    val estMinutes: Double,
    val more: List<MoreChapter>
) {
    val hasMore: Boolean get() = more.isNotEmpty()
    val moreMinutes: Double get() = more.sumOf { it.minutes }
}

data class Sight(
    val id: String,
    val name: String,
    val day: Int,
    val date: String,
    val note: String,
    val kid: List<Track>,
    val adult: List<Track>
) {
    fun tracks(kidMode: Boolean) = if (kidMode) kid else adult
}

data class SightArt(val emoji: String, val color: Long, val wiki: List<String>)

class TourRepository(private val context: Context) {

    val sights: List<Sight> by lazy { loadManifest() }
    val art: Map<String, SightArt> by lazy { loadArt() }

    fun sightsByDay(): List<Pair<Int, List<Sight>>> =
        sights.groupBy { it.day }.toSortedMap().map { it.key to it.value }

    fun sight(id: String): Sight = sights.first { it.id == id }

    /** Raw narration text for a track file, title line stripped. */
    fun trackText(file: String): String {
        val raw = context.assets.open("tour/$file").bufferedReader().use { it.readText() }
        return raw.lines().dropWhile { it.isBlank() }
            .let { if (it.firstOrNull()?.startsWith("#") == true) it.drop(1) else it }
            .joinToString("\n").trim()
    }

    /** Pre-rendered audio in assets, if the user ran generate_audio.py. */
    fun audioAssetPath(trackFile: String): String? {
        val base = "tour/audio/" + trackFile.removePrefix("content/").removeSuffix(".md")
        for (ext in listOf("mp3", "wav")) {
            val p = "$base.$ext"
            val dir = p.substringBeforeLast('/')
            val name = p.substringAfterLast('/')
            runCatching {
                if (context.assets.list(dir)?.contains(name) == true) return p
            }
        }
        return null
    }

    private val bundledImages: Set<String> by lazy {
        runCatching { context.assets.list("tour/images")?.toSet() }.getOrNull() ?: emptySet()
    }

    /** Locally bundled image (from fetch_images.py). App is fully offline. */
    fun localImageAsset(sightId: String, index: Int): String? {
        val name = "$sightId-$index.jpg"
        return if (name in bundledImages) "file:///android_asset/tour/images/$name" else null
    }

    private fun loadManifest(): List<Sight> {
        val json = context.assets.open("tour/manifest.json").bufferedReader().use { it.readText() }
        val root = JSONObject(json)
        val out = mutableListOf<Sight>()
        val arr = root.getJSONArray("sights")
        for (i in 0 until arr.length()) {
            val s = arr.getJSONObject(i)
            val tracks = s.getJSONObject("tracks")
            fun parse(key: String): List<Track> {
                val a = tracks.getJSONArray(key)
                val list = mutableListOf<Track>()
                for (j in 0 until a.length()) {
                    val t = a.getJSONObject(j)
                    val chapters = mutableListOf<MoreChapter>()
                    // New shape: tell_me_more is an array of chapter objects.
                    val moreArr = t.optJSONArray("tell_me_more")
                    if (moreArr != null) {
                        for (k in 0 until moreArr.length()) {
                            val c = moreArr.getJSONObject(k)
                            chapters += MoreChapter(
                                file = c.getString("file"),
                                title = c.optString("title", "Tell me more"),
                                minutes = c.optDouble("est_minutes", 1.5)
                            )
                        }
                    } else {
                        // Legacy shape: a single tell_me_more object.
                        t.optJSONObject("tell_me_more")?.let { more ->
                            chapters += MoreChapter(
                                file = more.getString("file"),
                                title = more.optString("title", "Tell me more"),
                                minutes = more.optDouble("est_minutes", 1.5)
                            )
                        }
                    }
                    list += Track(
                        file = t.getString("file"),
                        title = t.getString("title"),
                        estMinutes = t.optDouble("est_minutes", 1.5),
                        more = chapters
                    )
                }
                return list
            }
            out += Sight(
                id = s.getString("id"),
                name = s.getString("name"),
                day = s.getInt("day"),
                date = s.optString("date"),
                note = s.optString("note"),
                kid = parse("kid"),
                adult = parse("adult")
            )
        }
        return out
    }

    private fun loadArt(): Map<String, SightArt> {
        val json = context.assets.open("tour/images.json").bufferedReader().use { it.readText() }
        val root = JSONObject(json)
        val map = mutableMapOf<String, SightArt>()
        for (key in root.keys()) {
            val o = root.getJSONObject(key)
            val wiki = mutableListOf<String>()
            val wa = o.getJSONArray("wiki")
            for (i in 0 until wa.length()) wiki += wa.getString(i)
            map[key] = SightArt(
                emoji = o.getString("emoji"),
                color = o.getString("color").removePrefix("#").toLong(16) or 0xFF000000,
                wiki = wiki
            )
        }
        return map
    }
}
