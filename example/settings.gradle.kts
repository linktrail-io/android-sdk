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
        // The LinkTrail SDK resolves from Maven Central (io.linktrail:sdk), same as any app.
        mavenCentral()
    }
}

rootProject.name = "kickflip-demo"
include(":app")
