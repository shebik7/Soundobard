package cz.soundobard

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.UUID

/**
 * One button on the board. Bundled sounds live in the APK assets ([assetName]),
 * sounds imported on the phone are copied into app storage ([fileName]).
 */
data class Sound(
    val id: String,
    val title: String,
    val assetName: String? = null,
    val fileName: String? = null,
    val hidden: Boolean = false,
) {
    val isBundled: Boolean get() = assetName != null
}

data class BoardSettings(
    val columns: Int = 3,
    val overlap: Boolean = false,
)

data class BoardState(
    val sounds: List<Sound> = emptyList(),
    val settings: BoardSettings = BoardSettings(),
)

class SoundRepository(private val context: Context) {

    private val stateFile = File(context.filesDir, "board.json")
    val soundsDir: File = File(context.filesDir, "sounds").apply { mkdirs() }

    /** Loads the saved board and merges it with the sounds currently bundled in the APK. */
    fun load(): BoardState {
        val saved = readState()
        val assets = listBundledAssets()

        val kept = saved.sounds.filter { sound ->
            when {
                sound.assetName != null -> sound.assetName in assets
                sound.fileName != null -> File(soundsDir, sound.fileName).exists()
                else -> false
            }
        }
        val known = kept.mapNotNull { it.assetName }.toSet()
        val added = assets
            .filter { it !in known }
            .sortedWith(String.CASE_INSENSITIVE_ORDER)
            .map { Sound(id = "asset:$it", title = titleFromFileName(it), assetName = it) }

        val state = saved.copy(sounds = kept + added)
        if (state != saved) save(state)
        return state
    }

    @Synchronized
    fun save(state: BoardState) {
        val json = JSONObject()
            .put("columns", state.settings.columns)
            .put("overlap", state.settings.overlap)
            .put("sounds", JSONArray().apply {
                state.sounds.forEach { s ->
                    put(JSONObject().apply {
                        put("id", s.id)
                        put("title", s.title)
                        s.assetName?.let { put("asset", it) }
                        s.fileName?.let { put("file", it) }
                        put("hidden", s.hidden)
                    })
                }
            })
        val tmp = File(stateFile.parentFile, stateFile.name + ".tmp")
        tmp.writeText(json.toString())
        if (!tmp.renameTo(stateFile)) {
            stateFile.writeText(json.toString())
            tmp.delete()
        }
    }

    /** Copies an audio file picked or shared by the user into app storage. */
    fun import(uri: Uri): Sound? {
        val resolver = context.contentResolver
        val displayName = resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)
            ?.use { c -> if (c.moveToFirst()) c.getString(0) else null }
            ?: uri.lastPathSegment?.substringAfterLast('/')
            ?: "Zvuk"
        val ext = displayName.substringAfterLast('.', "mp3").lowercase().takeIf { it.length in 2..4 } ?: "mp3"
        val id = UUID.randomUUID().toString()
        val fileName = "$id.$ext"
        val target = File(soundsDir, fileName)
        return try {
            resolver.openInputStream(uri)?.use { input ->
                target.outputStream().use { output -> input.copyTo(output) }
            } ?: return null
            Sound(id = "file:$id", title = titleFromFileName(displayName), fileName = fileName)
        } catch (e: Exception) {
            target.delete()
            null
        }
    }

    fun deleteFile(sound: Sound) {
        sound.fileName?.let { File(soundsDir, it).delete() }
    }

    private fun listBundledAssets(): List<String> =
        (context.assets.list("") ?: emptyArray())
            .filter { it.substringAfterLast('.', "").lowercase() in AUDIO_EXTENSIONS }

    private fun readState(): BoardState {
        if (!stateFile.exists()) return BoardState()
        return try {
            val json = JSONObject(stateFile.readText())
            val arr = json.optJSONArray("sounds") ?: JSONArray()
            val sounds = (0 until arr.length()).map { i ->
                val o = arr.getJSONObject(i)
                Sound(
                    id = o.getString("id"),
                    title = o.getString("title"),
                    assetName = o.optString("asset").ifEmpty { null },
                    fileName = o.optString("file").ifEmpty { null },
                    hidden = o.optBoolean("hidden", false),
                )
            }
            BoardState(
                sounds = sounds,
                settings = BoardSettings(
                    columns = json.optInt("columns", 3).coerceIn(2, 4),
                    overlap = json.optBoolean("overlap", false),
                ),
            )
        } catch (e: Exception) {
            BoardState()
        }
    }

    companion object {
        val AUDIO_EXTENSIONS = setOf("mp3", "ogg", "wav", "m4a", "aac", "flac")

        fun titleFromFileName(name: String): String =
            name.substringBeforeLast('.')
                .replace('_', ' ')
                .trim()
                .ifEmpty { name }
    }
}
