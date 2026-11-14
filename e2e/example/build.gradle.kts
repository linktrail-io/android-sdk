import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
}

// The KickFlip example app the Maestro flows in ../scripts drive. It depends on the PUBLISHED SDK
// (io.linktrail:sdk from Maven Central, version in ../gradle/libs.versions.toml), not on SDK source.
//
// Build-time settings. Each is read, in order, from an environment variable, a Gradle property
// (-P… or ~/.gradle/gradle.properties) and the untracked e2e/local.properties.
// Never commit a real key, and never print it here.
val localProps = Properties().apply {
    val f = rootProject.file("local.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}

fun setting(env: String, key: String): String? =
    (System.getenv(env) ?: findProperty(key)?.toString() ?: localProps.getProperty(key))
        ?.trim()
        ?.takeIf { it.isNotEmpty() }

/** Escapes a value for a Java string literal in BuildConfig. */
fun javaString(value: String): String =
    "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"") + "\""

// Workspace SDK key (lt_live_…). Empty means "not set": the app then falls back to a placeholder key,
// which the backend rejects, and logs a warning at runtime. Fork CI builds this way.
val linktrailApiKey: String = setting("LINKTRAIL_KEY", "linktrail.apiKey").orEmpty()
// The LinkTrail-hosted link host: drives both the App Links intent filter and the SDK's linkDomains.
val linktrailLinkHost: String = setting("LINKTRAIL_LINK_HOST", "linktrail.linkHost") ?: "kick.linktrail.io"
// A second link host, the workspace's custom domain. Empty = the link host only.
val linktrailCustomLinkHost: String = setting("LINKTRAIL_CUSTOM_LINK_HOST", "linktrail.customLinkHost") ?: linktrailLinkHost
// Debug-only backend override (bare host URL). Empty = production.
val linktrailBase: String = setting("LINKTRAIL_BASE", "linktrail.base").orEmpty()
// SDK logging in debug builds (release builds never log). The e2e script asserts on these lines.
val linktrailLogs: Boolean = setting("LINKTRAIL_LOGS", "linktrail.logs")?.toBooleanStrictOrNull() ?: true

if (linktrailApiKey.isEmpty()) {
    logger.warn("KickFlip e2e example: no LinkTrail API key set (linktrail.apiKey / LINKTRAIL_KEY); using a placeholder.")
}

android {
    namespace = "io.linktrail.example"
    compileSdk = 36

    defaultConfig {
        applicationId = "io.linktrail.demo.store" // install id and Maestro appId (namespace stays io.linktrail.example)
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "e2e"
        buildConfigField("String", "LINKTRAIL_API_KEY", javaString(linktrailApiKey))
        buildConfigField("String", "LINKTRAIL_LINK_HOST", javaString(linktrailLinkHost))
        buildConfigField("String", "LINKTRAIL_CUSTOM_LINK_HOST", javaString(linktrailCustomLinkHost))
        buildConfigField("boolean", "LINKTRAIL_LOGS", linktrailLogs.toString())
        buildConfigField("boolean", "LINKTRAIL_RELEASE_LOGS", "false")
        manifestPlaceholders["linktrailLinkHost"] = linktrailLinkHost
        manifestPlaceholders["linktrailCustomLinkHost"] = linktrailCustomLinkHost
        manifestPlaceholders["linktrailBase"] = linktrailBase
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }
    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.8" // matches Kotlin 1.9.22
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    // The published SDK from Maven Central: what this suite tests.
    implementation(libs.linktrail.sdk)

    implementation(platform("androidx.compose:compose-bom:2024.01.00"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    debugImplementation("androidx.compose.ui:ui-tooling")
    implementation("androidx.compose.material3:material3:1.2.0")
    implementation("androidx.activity:activity-compose:1.8.2")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")
    implementation(libs.androidx.core.ktx)
    // The app code uses coroutines directly (the SDK keeps its own on its runtime classpath only).
    implementation(libs.kotlinx.coroutines.android)
}
