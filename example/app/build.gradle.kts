import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// API key from the untracked local.properties — never commit a real lt_live_ key.
val linktrailApiKey: String = Properties().apply {
    val file = rootProject.file("local.properties")
    if (file.exists()) file.inputStream().use { load(it) }
}.getProperty("linktrail.apiKey").orEmpty().trim()

android {
    namespace = "io.linktrail.example"
    compileSdk = 34

    defaultConfig {
        applicationId = "io.linktrail.example"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "0.0.1"
        buildConfigField("String", "LINKTRAIL_API_KEY", "\"$linktrailApiKey\"")
    }

    buildTypes {
        release { isMinifyEnabled = false }
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.8"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    // The published LinkTrail SDK — the binary AAR from this repo's Maven layout.
    implementation("linktrail.io:sdk:0.0.3")

    implementation(platform("androidx.compose:compose-bom:2024.01.00"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    debugImplementation("androidx.compose.ui:ui-tooling")
    implementation("androidx.compose.material3:material3:1.2.0")
    implementation("androidx.activity:activity-compose:1.8.2")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.7.0")
    implementation("androidx.core:core-ktx:1.12.0")
}
