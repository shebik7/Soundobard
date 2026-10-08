package cz.soundobard

import android.app.Application
import android.net.Uri
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@OptIn(ExperimentalCoroutinesApi::class)
class BoardViewModel(app: Application) : AndroidViewModel(app) {

    private val repository = SoundRepository(app)
    val player = SoundPlayer(app, repository.soundsDir)

    // Single-threaded so saves are written in the order they were made.
    private val io = Dispatchers.IO.limitedParallelism(1)

    var state by mutableStateOf(BoardState())
        private set
    var loaded by mutableStateOf(false)
        private set

    private val loadJob = viewModelScope.launch {
        state = withContext(io) { repository.load() }
        loaded = true
    }

    fun play(sound: Sound) = player.toggle(sound, state.settings.overlap)

    fun importSounds(uris: List<Uri>, onDone: (Int) -> Unit = {}) {
        if (uris.isEmpty()) return
        viewModelScope.launch {
            val imported = withContext(Dispatchers.IO) { uris.mapNotNull { repository.import(it) } }
            loadJob.join()
            if (imported.isNotEmpty()) update { it.copy(sounds = it.sounds + imported) }
            onDone(imported.size)
        }
    }

    /** Bundled sounds back in file-name order, sounds added on the phone after them. */
    fun resetOrder() = update { s ->
        s.copy(sounds = s.sounds.sortedWith(
            compareBy<Sound> { it.assetName == null }.thenBy(String.CASE_INSENSITIVE_ORDER) { it.assetName ?: "" }
        ))
    }

    fun move(fromId: String, toId: String) {
        val list = state.sounds.toMutableList()
        val from = list.indexOfFirst { it.id == fromId }
        val to = list.indexOfFirst { it.id == toId }
        if (from < 0 || to < 0 || from == to) return
        list.add(to, list.removeAt(from))
        update { it.copy(sounds = list) }
    }

    fun rename(sound: Sound, title: String) {
        val clean = title.trim().ifEmpty { return }
        updateSound(sound.id) { it.copy(title = clean) }
    }

    fun setHidden(sound: Sound, hidden: Boolean) {
        if (hidden) player.stop(sound.id)
        updateSound(sound.id) { it.copy(hidden = hidden) }
    }

    fun delete(sound: Sound) {
        player.stop(sound.id)
        update { s -> s.copy(sounds = s.sounds.filterNot { it.id == sound.id }) }
        viewModelScope.launch(io) { repository.deleteFile(sound) }
    }

    fun setColumns(columns: Int) = update { it.copy(settings = it.settings.copy(columns = columns)) }

    fun setOverlap(overlap: Boolean) = update { it.copy(settings = it.settings.copy(overlap = overlap)) }

    private fun updateSound(id: String, change: (Sound) -> Sound) =
        update { s -> s.copy(sounds = s.sounds.map { if (it.id == id) change(it) else it }) }

    private fun update(change: (BoardState) -> BoardState) {
        if (!loaded) return
        val next = change(state)
        state = next
        viewModelScope.launch(io) { repository.save(next) }
    }

    override fun onCleared() {
        player.stopAll()
    }
}
