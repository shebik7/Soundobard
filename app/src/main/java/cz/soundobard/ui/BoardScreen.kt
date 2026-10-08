package cz.soundobard.ui

import android.view.HapticFeedbackConstants
import androidx.compose.animation.animateColorAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Settings
import androidx.compose.material.icons.rounded.Stop
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import cz.soundobard.BoardViewModel
import cz.soundobard.Sound

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BoardScreen(viewModel: BoardViewModel, onOpenSettings: () -> Unit) {
    val state = viewModel.state
    val playing = viewModel.player.playing
    val visible = state.sounds.filterNot { it.hidden }
    val columns = state.settings.columns

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Soundboard", fontWeight = FontWeight.SemiBold) },
                actions = {
                    if (playing.isNotEmpty()) {
                        IconButton(onClick = { viewModel.player.stopAll() }) {
                            Icon(Icons.Rounded.Stop, contentDescription = "Zastavit vše")
                        }
                    }
                    IconButton(onClick = onOpenSettings) {
                        Icon(Icons.Rounded.Settings, contentDescription = "Nastavení")
                    }
                },
            )
        },
    ) { padding ->
        if (viewModel.loaded && visible.isEmpty()) {
            EmptyBoard(Modifier.padding(padding), onOpenSettings)
        } else {
            LazyVerticalGrid(
                columns = GridCells.Fixed(columns),
                modifier = Modifier.fillMaxSize().padding(padding),
                contentPadding = PaddingValues(12.dp),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                items(visible, key = { it.id }) { sound ->
                    SoundButton(
                        sound = sound,
                        columns = columns,
                        isPlaying = sound.id in playing,
                        onClick = { viewModel.play(sound) },
                    )
                }
            }
        }
    }
}

@Composable
private fun SoundButton(sound: Sound, columns: Int, isPlaying: Boolean, onClick: () -> Unit) {
    val view = LocalView.current
    val colors = MaterialTheme.colorScheme
    val container by animateColorAsState(
        if (isPlaying) colors.primary else colors.surfaceContainerHigh, label = "container",
    )
    val content by animateColorAsState(
        if (isPlaying) colors.onPrimary else colors.onSurface, label = "content",
    )
    val (height, fontSize) = when (columns) {
        2 -> 104.dp to 19.sp
        4 -> 84.dp to 14.sp
        else -> 92.dp to 16.sp
    }

    Surface(
        onClick = {
            view.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP)
            onClick()
        },
        modifier = Modifier.fillMaxWidth().height(height),
        shape = RoundedCornerShape(18.dp),
        color = container,
        contentColor = content,
    ) {
        Box(Modifier.fillMaxSize().padding(horizontal = 8.dp, vertical = 6.dp), contentAlignment = Alignment.Center) {
            Text(
                text = sound.title,
                fontSize = fontSize,
                lineHeight = fontSize * 1.15f,
                fontWeight = FontWeight.SemiBold,
                textAlign = TextAlign.Center,
                maxLines = 3,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
private fun EmptyBoard(modifier: Modifier, onOpenSettings: () -> Unit) {
    Column(
        modifier = modifier.fillMaxSize().padding(32.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            "Zatím tu nejsou žádné zvuky.",
            style = MaterialTheme.typography.titleMedium,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(16.dp))
        FilledTonalButton(onClick = onOpenSettings) { Text("Přidat zvuky") }
    }
}
