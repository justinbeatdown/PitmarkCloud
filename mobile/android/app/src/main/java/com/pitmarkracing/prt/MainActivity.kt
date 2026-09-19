package com.pitmarkracing.prt

import android.app.Application
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Assessment
import androidx.compose.material.icons.filled.Dashboard
import androidx.compose.material.icons.filled.Flag
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.SportsMotorsports
import androidx.compose.material.icons.filled.Upload
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.Locale

private val PitmarkOrange = Color(0xFFFF5500)
private val PitmarkBlack = Color(0xFF08090A)
private val PitmarkCard = Color(0xFF141619)
private val PitmarkBorder = Color(0xFF2A2E33)
private val PitmarkText = Color(0xFFF4F1EB)
private val PitmarkMuted = Color(0xFF9DA3AA)

private val PitmarkScheme = darkColorScheme(
    primary = PitmarkOrange,
    background = PitmarkBlack,
    surface = PitmarkCard,
    onPrimary = Color.Black,
    onBackground = PitmarkText,
    onSurface = PitmarkText
)

class MainActivity : ComponentActivity() {
    private var incomingPairCode by mutableStateOf<String?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        incomingPairCode = intent?.data?.getQueryParameter("code")
        setContent {
            MaterialTheme(colorScheme = PitmarkScheme) {
                Surface(modifier = Modifier.fillMaxSize(), color = PitmarkBlack) {
                    PrtApp(initialPairCode = incomingPairCode)
                }
            }
        }
    }

    override fun onNewIntent(intent: android.content.Intent) {
        super.onNewIntent(intent)
        incomingPairCode = intent.data?.getQueryParameter("code")
    }
}

private class CredentialStore(application: Application) {
    private val masterKey = MasterKey.Builder(application)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()

    private val prefs = EncryptedSharedPreferences.create(
        application,
        "prt_secure",
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )

    fun read(): PrtCredentials? {
        val id = prefs.getString("device_id", "").orEmpty()
        val token = prefs.getString("token", "").orEmpty()
        return if (id.isBlank() || token.isBlank()) null else PrtCredentials(id, token)
    }

    fun save(credentials: PrtCredentials) {
        prefs.edit()
            .putString("device_id", credentials.deviceId.trim())
            .putString("token", credentials.token.trim())
            .apply()
    }

    fun ensure(): PrtCredentials {
        read()?.let { return it }
        val id = UUID.randomUUID().toString().replace("-", "")
        val bytes = ByteArray(32)
        SecureRandom().nextBytes(bytes)
        val token = bytes.joinToString("") { "%02x".format(it) }
        val created = PrtCredentials(id, token)
        save(created)
        return created
    }

    fun isPaired(): Boolean = prefs.getBoolean("paired", false)

    fun markPaired(value: Boolean) {
        prefs.edit().putBoolean("paired", value).apply()
    }

    fun clear() {
        prefs.edit().clear().apply()
    }
}

class PrtViewModel(application: Application) : AndroidViewModel(application) {
    private val api = PrtApi()
    private val store = CredentialStore(application)

    var credentials by mutableStateOf<PrtCredentials?>(store.ensure())
        private set
    var paired by mutableStateOf(store.isPaired())
        private set
    var dashboard by mutableStateOf<DashboardPayload?>(null)
        private set
    var sessions by mutableStateOf<List<RaceResult>>(emptyList())
        private set
    var loading by mutableStateOf(false)
        private set
    var error by mutableStateOf<String?>(null)
        private set
    var notice by mutableStateOf<String?>(null)
        private set

    init {
        registerPhone()
        if (paired) refreshAll()
    }

    private fun registerPhone() {
        val auth = credentials ?: return
        viewModelScope.launch {
            try {
                withContext(Dispatchers.IO) { api.registerDevice(auth) }
            } catch (t: Throwable) {
                error = t.message ?: "Could not register this phone with Pitmark Cloud."
            }
        }
    }

    fun claimPairing(code: String) {
        val auth = credentials ?: return
        val clean = code.filter { it.isDigit() }
        if (clean.length != 6) {
            error = "Enter the 6-digit code shown in desktop PRT."
            return
        }
        viewModelScope.launch {
            loading = true
            error = null
            try {
                val name = withContext(Dispatchers.IO) { api.claimPairing(auth, clean) }
                store.markPaired(true)
                paired = true
                notice = "Paired with " + name
                refreshAll()
            } catch (t: Throwable) {
                error = t.message ?: "Could not pair this phone."
            } finally {
                loading = false
            }
        }
    }

    fun disconnect() {
        store.clear()
        credentials = store.ensure()
        paired = false
        dashboard = null
        sessions = emptyList()
        error = null
        notice = null
    }

    fun refreshAll() {
        val auth = credentials ?: return
        viewModelScope.launch {
            loading = true
            error = null
            try {
                val result = withContext(Dispatchers.IO) { api.dashboard(auth) }
                val history = withContext(Dispatchers.IO) { api.sessions(auth, 50) }
                dashboard = result
                sessions = history
            } catch (t: Throwable) {
                error = t.message ?: "Could not reach Pitmark Cloud."
            } finally {
                loading = false
            }
        }
    }

    fun shareRaceCard() {
        val auth = credentials ?: return
        viewModelScope.launch {
            loading = true
            error = null
            try {
                notice = withContext(Dispatchers.IO) { api.shareLatestRaceCard(auth) }
            } catch (t: Throwable) {
                error = t.message ?: "Race Card share failed."
            } finally {
                loading = false
            }
        }
    }

    fun clearNotice() {
        notice = null
    }
}

@Composable
private fun PrtApp(initialPairCode: String? = null, vm: PrtViewModel = viewModel()) {
    var tab by remember { mutableIntStateOf(0) }
    var showSettings by remember { mutableStateOf(false) }
    val snackbar = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()

    LaunchedEffect(vm.error) {
        vm.error?.let { snackbar.showSnackbar(it) }
    }
    LaunchedEffect(vm.notice) {
        vm.notice?.let {
            snackbar.showSnackbar(it)
            vm.clearNotice()
        }
    }

    LaunchedEffect(initialPairCode, vm.paired) {
        if (!vm.paired && !initialPairCode.isNullOrBlank()) {
            vm.claimPairing(initialPairCode)
        }
    }

    if (!vm.paired) {
        PairingScreen(
            initialCode = initialPairCode.orEmpty(),
            loading = vm.loading,
            onPair = vm::claimPairing
        )
        return
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbar) },
        topBar = {
            AppHeader(
                dashboard = vm.dashboard,
                loading = vm.loading,
                onRefresh = vm::refreshAll,
                onSettings = { showSettings = true }
            )
        },
        bottomBar = {
            NavigationBar(containerColor = Color(0xFF0E1012)) {
                val entries = listOf(
                    Triple("Home", Icons.Default.Dashboard, 0),
                    Triple("Races", Icons.Default.Flag, 1),
                    Triple("Live", Icons.Default.SportsMotorsports, 2),
                    Triple("Control", Icons.Default.Assessment, 3)
                )
                entries.forEach { (label, icon, index) ->
                    NavigationBarItem(
                        selected = tab == index,
                        onClick = { tab = index },
                        icon = { Icon(icon, contentDescription = label) },
                        label = { Text(label) }
                    )
                }
            }
        },
        containerColor = PitmarkBlack
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            when (tab) {
                0 -> HomeScreen(vm.dashboard, vm.sessions)
                1 -> RaceHistoryScreen(vm.sessions)
                2 -> LiveScreen(vm.dashboard)
                else -> ControlScreen(
                    dashboard = vm.dashboard,
                    onRefresh = vm::refreshAll,
                    onShare = vm::shareRaceCard
                )
            }

            if (vm.loading && vm.dashboard == null) {
                CircularProgressIndicator(
                    modifier = Modifier.align(Alignment.Center),
                    color = PitmarkOrange
                )
            }
        }
    }

    if (showSettings) {
        SettingsDialog(
            credentials = vm.credentials,
            onDismiss = { showSettings = false },
            onSave = { id, token ->
                vm.saveCredentials(id, token)
                showSettings = false
            },
            onDisconnect = {
                showSettings = false
                vm.disconnect()
            }
        )
    }
}

@Composable
private fun AppHeader(
    dashboard: DashboardPayload?,
    loading: Boolean,
    onRefresh: () -> Unit,
    onSettings: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 18.dp, vertical = 14.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                "PITMARK RACING TOOLS",
                style = MaterialTheme.typography.labelMedium,
                color = PitmarkOrange,
                fontWeight = FontWeight.Black
            )
            Text(
                dashboard?.driver?.displayName ?: "PRT Driver",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold
            )
        }
        if (loading) {
            CircularProgressIndicator(
                modifier = Modifier.width(24.dp),
                strokeWidth = 2.dp,
                color = PitmarkOrange
            )
        } else {
            IconButton(onClick = onRefresh) {
                Icon(Icons.Default.Refresh, contentDescription = "Refresh")
            }
        }
        IconButton(onClick = onSettings) {
            Icon(Icons.Default.Settings, contentDescription = "Settings")
        }
    }
}

@Composable
private fun PairingScreen(onSave: (String, String) -> Unit) {
    var deviceId by remember { mutableStateOf("") }
    var token by remember { mutableStateOf("") }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.Center
    ) {
        Text(
            "PRT MOBILE",
            color = PitmarkOrange,
            style = MaterialTheme.typography.labelLarge,
            fontWeight = FontWeight.Black
        )
        Text(
            "Your race data, away from the rig.",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold
        )
        Spacer(Modifier.height(12.dp))
        Text(
            "Pair this first build with the same PRT device credentials already trusted by Pitmark Cloud. QR pairing is the next step before public release.",
            color = PitmarkMuted
        )
        Spacer(Modifier.height(24.dp))
        OutlinedTextField(
            value = deviceId,
            onValueChange = { deviceId = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("PRT device ID") },
            singleLine = true
        )
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(
            value = token,
            onValueChange = { token = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Device token") },
            singleLine = true
        )
        Spacer(Modifier.height(18.dp))
        Button(
            onClick = { onSave(deviceId, token) },
            modifier = Modifier.fillMaxWidth(),
            enabled = deviceId.length >= 16 && token.length >= 32
        ) {
            Text("CONNECT TO PRT")
        }
    }
}

@Composable
private fun HomeScreen(dashboard: DashboardPayload?, sessions: List<RaceResult>) {
    val data = dashboard ?: DashboardPayload()
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item {
            StatusHero(data)
        }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                StatCard("SESSIONS", data.summary.sessions.toString(), Modifier.weight(1f))
                StatCard("LAPS", data.summary.laps.toString(), Modifier.weight(1f))
            }
        }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                StatCard("AVG FINISH", position(data.summary.avgFinish), Modifier.weight(1f))
                StatCard("INCIDENTS", data.summary.incidents.toString(), Modifier.weight(1f))
            }
        }
        item {
            SectionTitle("RECENT RACES")
        }
        items(sessions.take(5)) { race ->
            RaceCard(race)
        }
        if (sessions.isEmpty()) {
            item { EmptyCard("No completed PRT race sessions are synced yet.") }
        }
    }
}

@Composable
private fun StatusHero(data: DashboardPayload) {
    Card(
        colors = CardDefaults.cardColors(containerColor = PitmarkCard),
        shape = RoundedCornerShape(18.dp)
    ) {
        Column(Modifier.padding(18.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    if (data.liveFresh) "LIVE NOW" else "DRIVER HUB",
                    color = if (data.liveFresh) PitmarkOrange else PitmarkMuted,
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.Black
                )
                Spacer(Modifier.weight(1f))
                Text(data.driver.plan.uppercase(Locale.US), color = PitmarkMuted)
            }
            Spacer(Modifier.height(8.dp))
            val live = data.liveSession
            Text(
                if (data.liveFresh && live != null) live.trackName else "PRT is connected.",
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.Bold
            )
            Text(
                if (data.liveFresh && live != null) {
                    live.carName + " • Lap " + live.lap + " • P" + live.position
                } else {
                    "Race history, telemetry and controls follow your PRT identity."
                },
                color = PitmarkMuted
            )
        }
    }
}

@Composable
private fun StatCard(label: String, value: String, modifier: Modifier = Modifier) {
    Card(
        modifier = modifier,
        colors = CardDefaults.cardColors(containerColor = PitmarkCard),
        shape = RoundedCornerShape(14.dp)
    ) {
        Column(Modifier.padding(16.dp)) {
            Text(label, color = PitmarkMuted, style = MaterialTheme.typography.labelSmall)
            Text(value, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Black)
        }
    }
}

@Composable
private fun RaceHistoryScreen(sessions: List<RaceResult>) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        item { SectionTitle("RACE HISTORY • LAST " + sessions.size) }
        items(sessions) { RaceCard(it) }
        if (sessions.isEmpty()) {
            item { EmptyCard("Your PRT race history will appear here after results sync.") }
        }
    }
}

@Composable
private fun RaceCard(race: RaceResult) {
    Card(
        colors = CardDefaults.cardColors(containerColor = PitmarkCard),
        shape = RoundedCornerShape(14.dp)
    ) {
        Column(Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(
                        race.trackName,
                        fontWeight = FontWeight.Bold,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    Text(race.carName, color = PitmarkMuted, style = MaterialTheme.typography.bodySmall)
                }
                Text(
                    if (race.finishingPosition > 0) "P" + race.finishingPosition else "—",
                    color = PitmarkOrange,
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.Black
                )
            }
            Spacer(Modifier.height(10.dp))
            HorizontalDivider(color = PitmarkBorder)
            Spacer(Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(18.dp)) {
                MiniStat("START", if (race.startingPosition > 0) "P" + race.startingPosition else "—")
                MiniStat("BEST", lapTime(race.bestLapTime))
                MiniStat("LAPS", race.laps.toString())
                MiniStat("INC", race.incidents.toString() + "x")
            }
        }
    }
}

@Composable
private fun LiveScreen(dashboard: DashboardPayload?) {
    val live = dashboard?.liveSession
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item { SectionTitle("LIVE SESSION") }
        if (live == null || dashboard.liveFresh.not()) {
            item {
                EmptyCard("No fresh PRT telemetry is streaming right now. Start iRacing with PRT on the PC and this page becomes the remote live view.")
            }
        } else {
            item {
                Card(
                    colors = CardDefaults.cardColors(containerColor = PitmarkCard),
                    shape = RoundedCornerShape(18.dp)
                ) {
                    Column(Modifier.padding(18.dp)) {
                        Text(live.flagText, color = PitmarkOrange, fontWeight = FontWeight.Black)
                        Text(live.trackName, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                        Text(live.carName, color = PitmarkMuted)
                    }
                }
            }
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    StatCard("POSITION", if (live.position > 0) "P" + live.position else "—", Modifier.weight(1f))
                    StatCard("LAP", live.lap.toString(), Modifier.weight(1f))
                }
            }
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    StatCard("BEST LAP", lapTime(live.bestLapTime), Modifier.weight(1f))
                    StatCard("DELTA", delta(live.delta), Modifier.weight(1f))
                }
            }
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    StatCard("FUEL LAPS", oneDecimal(live.fuelLapsRemaining), Modifier.weight(1f))
                    StatCard("INCIDENTS", live.incidentCount.toString(), Modifier.weight(1f))
                }
            }
            item {
                Card(colors = CardDefaults.cardColors(containerColor = PitmarkCard)) {
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(16.dp),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        MiniStat("SPEED", oneDecimal(live.speedMph) + " mph")
                        MiniStat("GEAR", live.gear.toString())
                        MiniStat("RPM", live.rpm.toString())
                        MiniStat("TRACK", oneDecimal(live.trackTempF) + "°")
                    }
                }
            }
        }
    }
}

@Composable
private fun ControlScreen(
    dashboard: DashboardPayload?,
    onRefresh: () -> Unit,
    onShare: () -> Unit
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item { SectionTitle("CONTROL") }
        item {
            ActionCard(
                title = "Refresh PRT",
                detail = "Pull the newest race history and live-session state from Pitmark Cloud.",
                button = "REFRESH",
                icon = { Icon(Icons.Default.Refresh, contentDescription = null) },
                onClick = onRefresh
            )
        }
        item {
            ActionCard(
                title = "Share Latest Race Card",
                detail = "Send the latest completed PRT result to your configured Pitmark Discord destination.",
                button = "SHARE",
                icon = { Icon(Icons.Default.Upload, contentDescription = null) },
                onClick = onShare
            )
        }
        item {
            Card(colors = CardDefaults.cardColors(containerColor = PitmarkCard)) {
                Column(Modifier.padding(16.dp)) {
                    Text("CONNECTION", color = PitmarkMuted, style = MaterialTheme.typography.labelSmall)
                    Spacer(Modifier.height(8.dp))
                    Text(
                        if (dashboard?.driver?.discordConnected == true) "Discord linked" else "Discord not linked",
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        "Plan: " + (dashboard?.driver?.plan ?: "—") + " • Status: " + (dashboard?.driver?.status ?: "—"),
                        color = PitmarkMuted
                    )
                }
            }
        }
        item {
            EmptyCard("Next control layer: PC online/offline state, overlay profile selection, remote session capture, Setup Vault and notification controls.")
        }
    }
}

@Composable
private fun ActionCard(
    title: String,
    detail: String,
    button: String,
    icon: @Composable () -> Unit,
    onClick: () -> Unit
) {
    Card(colors = CardDefaults.cardColors(containerColor = PitmarkCard)) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier.width(38.dp),
                contentAlignment = Alignment.Center
            ) { icon() }
            Spacer(Modifier.width(8.dp))
            Column(Modifier.weight(1f)) {
                Text(title, fontWeight = FontWeight.Bold)
                Text(detail, color = PitmarkMuted, style = MaterialTheme.typography.bodySmall)
            }
            Spacer(Modifier.width(10.dp))
            OutlinedButton(onClick = onClick) { Text(button) }
        }
    }
}

@Composable
private fun SectionTitle(text: String) {
    Text(
        text,
        color = PitmarkMuted,
        style = MaterialTheme.typography.labelLarge,
        fontWeight = FontWeight.Black
    )
}

@Composable
private fun MiniStat(label: String, value: String) {
    Column {
        Text(label, color = PitmarkMuted, style = MaterialTheme.typography.labelSmall)
        Text(value, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun EmptyCard(text: String) {
    Card(colors = CardDefaults.cardColors(containerColor = PitmarkCard)) {
        Text(text, color = PitmarkMuted, modifier = Modifier.padding(16.dp))
    }
}

@Composable
private fun SettingsDialog(
    credentials: PrtCredentials?,
    onDismiss: () -> Unit,
    onSave: (String, String) -> Unit,
    onDisconnect: () -> Unit
) {
    var id by remember { mutableStateOf(credentials?.deviceId.orEmpty()) }
    var token by remember { mutableStateOf(credentials?.token.orEmpty()) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("PRT Connection") },
        text = {
            Column {
                OutlinedTextField(
                    value = id,
                    onValueChange = { id = it },
                    label = { Text("Device ID") },
                    singleLine = true
                )
                Spacer(Modifier.height(10.dp))
                OutlinedTextField(
                    value = token,
                    onValueChange = { token = it },
                    label = { Text("Device token") },
                    singleLine = true
                )
                Spacer(Modifier.height(12.dp))
                TextButton(onClick = onDisconnect) {
                    Text("Disconnect this phone")
                }
            }
        },
        confirmButton = {
            Button(
                onClick = { onSave(id, token) },
                enabled = id.length >= 16 && token.length >= 32
            ) { Text("SAVE") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("CANCEL") }
        }
    )
}

private fun lapTime(seconds: Double): String {
    if (seconds <= 0.0) return "—"
    val minutes = (seconds / 60).toInt()
    val remaining = seconds - minutes * 60
    return if (minutes > 0) String.format(Locale.US, "%d:%06.3f", minutes, remaining)
    else String.format(Locale.US, "%.3f", remaining)
}

private fun oneDecimal(value: Double): String =
    if (value <= 0.0) "—" else String.format(Locale.US, "%.1f", value)

private fun position(value: Double): String =
    if (value <= 0.0) "—" else "P" + String.format(Locale.US, "%.1f", value)

private fun delta(value: Double): String =
    if (value == 0.0) "±0.000" else String.format(Locale.US, "%+.3f", value)
