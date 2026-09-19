package com.pitmarkracing.prt

import okhttp3.FormBody
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException

data class PrtCredentials(val deviceId: String, val token: String)

data class DriverInfo(
    val displayName: String = "Pitmark Racer",
    val plan: String = "free",
    val status: String = "active",
    val discordConnected: Boolean = false
)

data class DriverSummary(
    val sessions: Int = 0,
    val laps: Int = 0,
    val bestLapTime: Double = 0.0,
    val avgFinish: Double = 0.0,
    val incidents: Int = 0
)

data class RaceResult(
    val sessionId: String = "",
    val date: String = "",
    val trackName: String = "Unknown Track",
    val carName: String = "Unknown Car",
    val sessionType: String = "iRacing Session",
    val laps: Int = 0,
    val bestLapTime: Double = 0.0,
    val averageLapTime: Double = 0.0,
    val startingPosition: Int = 0,
    val finishingPosition: Int = 0,
    val incidents: Int = 0,
    val consistency: Double = 0.0
)

data class LiveSession(
    val trackName: String = "",
    val carName: String = "",
    val lap: Int = 0,
    val position: Int = 0,
    val currentLapTime: Double = 0.0,
    val bestLapTime: Double = 0.0,
    val delta: Double = 0.0,
    val speedMph: Double = 0.0,
    val gear: Int = 0,
    val rpm: Int = 0,
    val fuelGallons: Double = 0.0,
    val fuelLapsRemaining: Double = 0.0,
    val incidentCount: Int = 0,
    val flagText: String = "GREEN",
    val trackTempF: Double = 0.0,
    val sessionLapsRemaining: Int = 0,
    val updatedAt: String = ""
)

data class DashboardPayload(
    val driver: DriverInfo = DriverInfo(),
    val summary: DriverSummary = DriverSummary(),
    val liveActive: Boolean = false,
    val liveFresh: Boolean = false,
    val liveSession: LiveSession? = null,
    val recentResults: List<RaceResult> = emptyList()
)

class PrtApi(
    private val baseUrl: String = "https://prt.pitmarkracing.com",
    private val client: OkHttpClient = OkHttpClient()
) {

    fun registerDevice(credentials: PrtCredentials) {
        val body = JSONObject()
            .put("device_id", credentials.deviceId)
            .put("device_secret", credentials.token)
            .toString()
            .toRequestBody("application/json".toMediaType())
        val request = Request.Builder()
            .url(baseUrl + "/api/device/register")
            .post(body)
            .build()
        client.newCall(request).execute().use { response ->
            val raw = response.body?.string().orEmpty()
            if (!response.isSuccessful && response.code != 409) {
                throw IOException(messageFrom(raw, response.code))
            }
        }
    }

    fun claimPairing(credentials: PrtCredentials, code: String): String {
        val body = JSONObject()
            .put("code", code)
            .toString()
            .toRequestBody("application/json".toMediaType())
        val request = Request.Builder()
            .url(baseUrl + "/api/prt/mobile/pair/claim?device_id=" + credentials.deviceId)
            .header("X-Pitmark-Device-Token", credentials.token)
            .post(body)
            .build()
        client.newCall(request).execute().use { response ->
            val raw = response.body?.string().orEmpty()
            if (!response.isSuccessful) throw IOException(messageFrom(raw, response.code))
            val json = JSONObject(raw)
            return json.optString("display_name", "Pitmark Racer")
        }
    }

    fun dashboard(credentials: PrtCredentials): DashboardPayload {
        val json = get("/api/prt/mobile/dashboard", credentials)
        val driver = json.optJSONObject("driver") ?: JSONObject()
        val summary = json.optJSONObject("summary") ?: JSONObject()
        val live = json.optJSONObject("live") ?: JSONObject()
        val liveJson = live.optJSONObject("session")
        return DashboardPayload(
            driver = DriverInfo(
                displayName = driver.optString("display_name", "Pitmark Racer"),
                plan = driver.optString("plan", "free"),
                status = driver.optString("status", "active"),
                discordConnected = driver.optBoolean("discord_connected", false)
            ),
            summary = DriverSummary(
                sessions = summary.optInt("sessions"),
                laps = summary.optInt("laps"),
                bestLapTime = summary.optDouble("best_lap_time"),
                avgFinish = summary.optDouble("avg_finish"),
                incidents = summary.optInt("incidents")
            ),
            liveActive = live.optBoolean("active"),
            liveFresh = live.optBoolean("fresh"),
            liveSession = liveJson?.let(::liveSession),
            recentResults = races(json.optJSONArray("recent_results") ?: JSONArray())
        )
    }

    fun sessions(credentials: PrtCredentials, limit: Int = 50): List<RaceResult> {
        val json = get("/api/prt/mobile/sessions?limit=" + limit, credentials)
        return races(json.optJSONArray("items") ?: JSONArray())
    }

    fun live(credentials: PrtCredentials): Pair<Boolean, LiveSession?> {
        val json = get("/api/prt/mobile/live", credentials)
        return json.optBoolean("fresh") to json.optJSONObject("session")?.let(::liveSession)
    }

    fun shareLatestRaceCard(credentials: PrtCredentials): String {
        val url = baseUrl + "/api/discord/share/racecard?device_id=" + credentials.deviceId
        val request = Request.Builder()
            .url(url)
            .header("X-Pitmark-Device-Token", credentials.token)
            .post(FormBody.Builder().build())
            .build()
        client.newCall(request).execute().use { response ->
            val body = response.body?.string().orEmpty()
            if (!response.isSuccessful) throw IOException(messageFrom(body, response.code))
            val json = JSONObject(body)
            return "Shared to " + json.optString("guild_name", "Discord") + " • #" +
                json.optString("channel_name", "pitmark")
        }
    }

    private fun get(path: String, credentials: PrtCredentials): JSONObject {
        val separator = if (path.contains("?")) "&" else "?"
        val url = baseUrl + path + separator + "device_id=" + credentials.deviceId
        val request = Request.Builder()
            .url(url)
            .header("X-Pitmark-Device-Token", credentials.token)
            .get()
            .build()
        client.newCall(request).execute().use { response ->
            val body = response.body?.string().orEmpty()
            if (!response.isSuccessful) throw IOException(messageFrom(body, response.code))
            return JSONObject(body)
        }
    }

    private fun messageFrom(body: String, code: Int): String {
        val detail = runCatching { JSONObject(body).optString("detail") }.getOrNull().orEmpty()
        return detail.ifBlank { "Pitmark Cloud request failed (" + code + ")." }
    }

    private fun races(array: JSONArray): List<RaceResult> = buildList {
        for (index in 0 until array.length()) {
            val item = array.optJSONObject(index) ?: continue
            add(
                RaceResult(
                    sessionId = item.optString("session_id"),
                    date = item.optString("date"),
                    trackName = item.optString("track_name", "Unknown Track"),
                    carName = item.optString("car_name", "Unknown Car"),
                    sessionType = item.optString("session_type", "iRacing Session"),
                    laps = item.optInt("laps"),
                    bestLapTime = item.optDouble("best_lap_time"),
                    averageLapTime = item.optDouble("average_lap_time"),
                    startingPosition = item.optInt("starting_position"),
                    finishingPosition = item.optInt("finishing_position"),
                    incidents = item.optInt("incidents"),
                    consistency = item.optDouble("consistency")
                )
            )
        }
    }

    private fun liveSession(item: JSONObject) = LiveSession(
        trackName = item.optString("track_name"),
        carName = item.optString("car_name"),
        lap = item.optInt("lap"),
        position = item.optInt("position"),
        currentLapTime = item.optDouble("current_lap_time"),
        bestLapTime = item.optDouble("best_lap_time"),
        delta = item.optDouble("delta"),
        speedMph = item.optDouble("speed_mph"),
        gear = item.optInt("gear"),
        rpm = item.optInt("rpm"),
        fuelGallons = item.optDouble("fuel_gallons"),
        fuelLapsRemaining = item.optDouble("fuel_laps_remaining"),
        incidentCount = item.optInt("incident_count"),
        flagText = item.optString("flag_text", "GREEN"),
        trackTempF = item.optDouble("track_temp_f"),
        sessionLapsRemaining = item.optInt("session_laps_remaining"),
        updatedAt = item.optString("updated_at")
    )
}
