package cz.soundobard.ui

import android.net.Uri
import android.view.HapticFeedbackConstants
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material.icons.rounded.Add
import androidx.compose.material.icons.rounded.Delete
import androidx.compose.material.icons.rounded.DragHandle
import androidx.compose.material.icons.rounded.PlayArrow
import androidx.compose.material.icons.rounded.RestartAlt
import androidx.compose.material.icons.rounded.Stop
import androidx.compose.material.icons.rounded.Visibility
import androidx.compose.material.icons.rounded.VisibilityOff
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import cz.soundobard.BoardViewModel
import cz.soundobard.Sound
import sh.calvin.reorderable.ReorderableItem
import sh.calvin.reorderable.rememberReorderableLazyListState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(viewModel: BoardViewModel, onBack: () -> Unit, onImport: (List<Uri>) -> Unit) {
    val state = viewModel.state
    val playing = viewModel.player.playing
    val view = LocalView.current

    var renaming by remember { mutableStateOf<Sound?>(null) }
    var deleting by remember { mutableStateOf<Sound?>(null) }

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris ->
        onImport(uris)
    }

    val listState = rememberLazyListState()
    val reorderState = rememberReorderableLazyListState(listState) { from, to ->
        viewModel.move(from.key as String, to.key as String)
        view.performHapticFeedback(HapticFeedbackConstants.CLOCK_TICK)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Nastavení", fontWeight = FontWeight.SemiBold) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Rounded.ArrowBack, contentDescription = "Zpět")
                    }
                },
            )
        },
    ) { padding ->
        LazyColumn(
            state = listState,
            modifier = Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 32.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            item(key = "header:add") {
                Column {
                    Button(
                        onClick = { picker.launch(arrayOf("audio/*")) },
                        modifier = Modifier.fillMaxWidth().height(52.dp),
                    ) {
                        Icon(Icons.Rounded.Add, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text("Přidat zvuky z telefonu")
                    }
                    Text(
                        "Tip: zvuk můžeš přidat i z jiné aplikace přes Sdílet → Soundboard.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 6.dp, start = 4.dp),
                    )
                }
            }

            item(key = "header:columns") {
                Column(Modifier.padding(top = 12.dp)) {
                    SectionTitle("Tlačítek vedle sebe")
                    SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                        val options = listOf(2, 3, 4)
                        options.forEachIndexed { index, value ->
                            SegmentedButton(
                                selected = state.settings.columns == value,
                                onClick = { viewModel.setColumns(value) },
                                shape = SegmentedButtonDefaults.itemShape(index, options.size),
                            ) { Text(value.toString()) }
                        }
                    }
                }
            }

            item(key = "header:overlap") {
                Row(
                    Modifier
                        .fillMaxWidth()
                        .padding(top = 8.dp)
                        .clickable { viewModel.setOverlap(!state.settings.overlap) }
                        .padding(vertical = 8.dp, horizontal = 4.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(Modifier.weight(1f)) {
                        Text("Přehrávat přes sebe", style = MaterialTheme.typography.bodyLarge)
                        Text(
                            "Vypnuto: nový zvuk zastaví ten předchozí.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Switch(checked = state.settings.overlap, onCheckedChange = viewModel::setOverlap)
                }
            }

            item(key = "header:list") {
                Column(Modifier.padding(top = 12.dp)) {
                    SectionTitle("Zvuky (${state.sounds.size})")
                    Text(
                        "Pořadí změníš přetažením za úchyt ≡, klepnutím na název ho přejmenuješ.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(start = 4.dp, bottom = 4.dp),
                    )
                    TextButton(onClick = viewModel::resetOrder) {
                        Icon(Icons.Rounded.RestartAlt, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text("Obnovit výchozí pořadí")
                    }
                }
            }

            items(state.sounds, key = { it.id }) { sound ->
                ReorderableItem(reorderState, key = sound.id) { isDragging ->
                    val elevation by animateDpAsState(if (isDragging) 6.dp else 0.dp, label = "elevation")
                    SoundRow(
                        sound = sound,
                        isPlaying = sound.id in playing,
                        elevation = elevation,
                        handle = {
                            IconButton(
                                onClick = {},
                                modifier = Modifier.draggableHandle(
                                    onDragStarted = {
                                        view.performHapticFeedback(HapticFeedbackConstants.LONG_PRESS)
                                    },
                                ),
                            ) {
                                Icon(Icons.Rounded.DragHandle, contentDescription = "Přesunout")
                            }
                        },
                        onRename = { renaming = sound },
                        onPreview = { viewModel.player.toggle(sound, overlap = false) },
                        onToggleHidden = { viewModel.setHidden(sound, !sound.hidden) },
                        onDelete = { deleting = sound },
                    )
                }
            }
        }
    }

    renaming?.let { sound ->
        RenameDialog(
            sound = sound,
            onDismiss = { renaming = null },
            onConfirm = { title ->
                viewModel.rename(sound, title)
                renaming = null
            },
        )
    }

    deleting?.let { sound ->
        AlertDialog(
            onDismissRequest = { deleting = null },
            title = { Text("Smazat zvuk?") },
            text = { Text("„${sound.title}“ bude z telefonu odstraněn.") },
            confirmButton = {
                TextButton(onClick = {
                    viewModel.delete(sound)
                    deleting = null
                }) { Text("Smazat") }
            },
            dismissButton = { TextButton(onClick = { deleting = null }) { Text("Zrušit") } },
        )
    }
}

@Composable
private fun SectionTitle(text: String) {
    Text(
        text,
        style = MaterialTheme.typography.titleSmall,
        color = MaterialTheme.colorScheme.primary,
        modifier = Modifier.padding(start = 4.dp, bottom = 8.dp),
    )
}

@Composable
private fun SoundRow(
    sound: Sound,
    isPlaying: Boolean,
    elevation: androidx.compose.ui.unit.Dp,
    handle: @Composable () -> Unit,
    onRename: () -> Unit,
    onPreview: () -> Unit,
    onToggleHidden: () -> Unit,
    onDelete: () -> Unit,
) {
    Surface(
        shape = RoundedCornerShape(14.dp),
        color = MaterialTheme.colorScheme.surfaceContainer,
        shadowElevation = elevation,
        tonalElevation = elevation,
    ) {
        Row(
            Modifier.fillMaxWidth().padding(vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            handle()
            Column(
                Modifier
                    .weight(1f)
                    .alpha(if (sound.hidden) 0.45f else 1f)
                    .clickable(onClick = onRename)
                    .padding(vertical = 8.dp, horizontal = 4.dp),
            ) {
                Text(
                    sound.title,
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.Medium,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    buildString {
                        append(if (sound.isBundled) "v aplikaci" else "přidaný v telefonu")
                        if (sound.hidden) append(" · skrytý")
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            IconButton(onClick = onPreview) {
                Icon(
                    if (isPlaying) Icons.Rounded.Stop else Icons.Rounded.PlayArrow,
                    contentDescription = if (isPlaying) "Zastavit" else "Přehrát",
                )
            }
            if (sound.isBundled) {
                IconButton(onClick = onToggleHidden) {
                    Icon(
                        if (sound.hidden) Icons.Rounded.VisibilityOff else Icons.Rounded.Visibility,
                        contentDescription = if (sound.hidden) "Zobrazit" else "Skrýt",
                    )
                }
            } else {
                IconButton(onClick = onDelete) {
                    Icon(Icons.Rounded.Delete, contentDescription = "Smazat")
                }
            }
        }
    }
}

@Composable
private fun RenameDialog(sound: Sound, onDismiss: () -> Unit, onConfirm: (String) -> Unit) {
    // Field is focused with the old title selected, so typing replaces it right away.
    var value by remember(sound.id) {
        mutableStateOf(TextFieldValue(sound.title, TextRange(0, sound.title.length)))
    }
    val focus = remember { FocusRequester() }
    LaunchedEffect(Unit) { focus.requestFocus() }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Přejmenovat") },
        text = {
            OutlinedTextField(
                value = value,
                onValueChange = { value = it },
                singleLine = true,
                modifier = Modifier.fillMaxWidth().focusRequester(focus),
            )
        },
        confirmButton = {
            TextButton(onClick = { onConfirm(value.text) }, enabled = value.text.isNotBlank()) { Text("Uložit") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Zrušit") } },
    )
}
