package cz.soundobard

import android.content.Intent
import android.media.AudioManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import cz.soundobard.ui.BoardScreen
import cz.soundobard.ui.SettingsScreen
import cz.soundobard.ui.SoundboardTheme

class MainActivity : ComponentActivity() {

    private val viewModel: BoardViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        // Hardware volume buttons control media volume even when nothing is playing.
        volumeControlStream = AudioManager.STREAM_MUSIC

        if (savedInstanceState == null) handleShare(intent)

        setContent {
            SoundboardTheme {
                var showSettings by rememberSaveable { mutableStateOf(false) }
                if (showSettings) {
                    BackHandler { showSettings = false }
                    SettingsScreen(
                        viewModel = viewModel,
                        onBack = { showSettings = false },
                        onImport = ::importAndReport,
                    )
                } else {
                    BoardScreen(
                        viewModel = viewModel,
                        onOpenSettings = { showSettings = true },
                    )
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleShare(intent)
    }

    private fun handleShare(intent: Intent?) {
        val uris = when (intent?.action) {
            Intent.ACTION_SEND -> listOfNotNull(intent.streamExtra())
            Intent.ACTION_SEND_MULTIPLE -> intent.streamListExtra()
            else -> emptyList()
        }
        importAndReport(uris)
    }

    private fun importAndReport(uris: List<Uri>) {
        if (uris.isEmpty()) return
        viewModel.importSounds(uris) { count ->
            val text = if (count > 0) "Přidáno zvuků: $count" else "Zvuk se nepodařilo přidat"
            Toast.makeText(this, text, Toast.LENGTH_SHORT).show()
        }
    }

    @Suppress("DEPRECATION")
    private fun Intent.streamExtra(): Uri? =
        if (Build.VERSION.SDK_INT >= 33) getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
        else getParcelableExtra(Intent.EXTRA_STREAM)

    @Suppress("DEPRECATION")
    private fun Intent.streamListExtra(): List<Uri> =
        (if (Build.VERSION.SDK_INT >= 33) getParcelableArrayListExtra(Intent.EXTRA_STREAM, Uri::class.java)
        else getParcelableArrayListExtra<Uri>(Intent.EXTRA_STREAM)) ?: emptyList()
}
