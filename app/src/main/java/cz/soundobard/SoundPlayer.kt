package cz.soundobard

import android.content.Context
import android.media.AudioAttributes
import android.media.MediaPlayer
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import java.io.File

/** Plays board sounds. Must be used from the main thread. */
class SoundPlayer(private val context: Context, private val soundsDir: File) {

    private val players = mutableMapOf<String, MediaPlayer>()

    /** Ids of sounds that are currently playing. */
    var playing by mutableStateOf<Set<String>>(emptySet())
        private set

    /** Starts [sound], or stops it when it is already playing. */
    fun toggle(sound: Sound, overlap: Boolean) {
        if (sound.id in players) {
            stop(sound.id)
            return
        }
        if (!overlap) stopAll()

        val player = MediaPlayer()
        try {
            player.setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                    .build()
            )
            when {
                sound.assetName != null -> context.assets.openFd(sound.assetName).use { fd ->
                    player.setDataSource(fd.fileDescriptor, fd.startOffset, fd.length)
                }
                sound.fileName != null -> player.setDataSource(File(soundsDir, sound.fileName).path)
                else -> {
                    player.release()
                    return
                }
            }
            player.setOnPreparedListener { if (players[sound.id] === it) it.start() }
            player.setOnCompletionListener { finished(sound.id, it) }
            player.setOnErrorListener { mp, _, _ ->
                finished(sound.id, mp)
                true
            }
            players[sound.id] = player
            playing = players.keys.toSet()
            player.prepareAsync()
        } catch (e: Exception) {
            players.remove(sound.id)
            playing = players.keys.toSet()
            player.release()
        }
    }

    fun stop(id: String) {
        players.remove(id)?.let { it.stopQuietly(); it.release() }
        playing = players.keys.toSet()
    }

    fun stopAll() {
        players.values.forEach { it.stopQuietly(); it.release() }
        players.clear()
        playing = emptySet()
    }

    private fun finished(id: String, player: MediaPlayer) {
        if (players[id] === player) players.remove(id)
        player.release()
        playing = players.keys.toSet()
    }

    private fun MediaPlayer.stopQuietly() {
        try {
            if (isPlaying) stop()
        } catch (_: IllegalStateException) {
        }
    }
}
