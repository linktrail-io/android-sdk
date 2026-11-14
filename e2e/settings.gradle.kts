// E2E harness for the PUBLISHED LinkTrail Android SDK. The KickFlip example below resolves
// io.linktrail:sdk from Maven Central, exactly like an app that integrates it. There is no SDK
// source in this repository and no local or custom repository for it.
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "linktrail-android-e2e"
include(":example")
