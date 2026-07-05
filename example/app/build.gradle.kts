import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// API key and release signing from the untracked local.properties — never commit real values.
val localProps = Properties().apply {
    val file = rootProject.file("local.properties")
    if (file.exists()) file.inputStream().use { load(it) }
}
val linktrailApiKey: String = localProps.getProperty("linktrail.apiKey").orEmpty().trim()

android {
    namespace = "io.linktrail.example"
    compileSdk = 35

    defaultConfig {
        applicationId = "io.linktrail.example"
        minSdk = 26
        targetSdk = 35
        versionCode = 2
        versionName = "0.0.2"
        buildConfigField("String", "LINKTRAIL_API_KEY", "\"$linktrailApiKey\"")
    }

    // Upload keystore for Play Store builds, configured in the untracked local.properties:
    //   linktrail.storeFile=upload-keystore.jks   (path relative to the example/ root)
    //   linktrail.storePassword=…
    //   linktrail.keyAlias=upload
    //   linktrail.keyPassword=…
    val storeFilePath = localProps.getProperty("linktrail.storeFile").orEmpty().trim()
    if (storeFilePath.isNotEmpty()) {
        signingConfigs {
            create("release") {
                storeFile = rootProject.file(storeFilePath)
                storePassword = localProps.getProperty("linktrail.storePassword")
                keyAlias = localProps.getProperty("linktrail.keyAlias")
                keyPassword = localProps.getProperty("linktrail.keyPassword")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.findByName("release")
        }
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
